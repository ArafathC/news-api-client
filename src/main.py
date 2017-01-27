from asyncio import get_event_loop, ensure_future, gather, sleep as aio_sleep
from collections import Counter
from concurrent.futures import TimeoutError
from datetime import datetime
from hashlib import sha256
from os import environ as env

from aiohttp import ClientSession

from aiomysql.sa import create_engine
from pymysql.err import IntegrityError
from models import article as article_model


MYSQL_CONNECTIONS = 10
SLEEPING_TIME = 60 * 60
db = {
    'user': 'user',
    'password': 'password',
    'host': 'mysql',
    'db': 'news',
}


def inject_engine(fnx):
    async def _wrapper(*args, **kwargs):
        engine = await create_engine(loop=get_event_loop(),
                                     maxsize=MYSQL_CONNECTIONS, **db)
        kwargs['engine'] = engine
        result = await fnx(*args, **kwargs)
        engine.close()
        await engine.wait_closed()
        return result
    return _wrapper


async def get_sources(timeout=5):
    url = 'https://newsapi.org/v1/sources'
    async with ClientSession() as session:
        async with session.get(url, timeout=timeout) as resp:
            resp = await resp.json()
    return [result['id'] for result in resp['sources']]


async def get_articles(source, api_key=env.get('API_KEY'), timeout=5):
    base = 'https://newsapi.org/v1/articles'
    query_string = f'?source={source}&apiKey={api_key}'  # noqa
    url = f'{base}{query_string}'
    async with ClientSession() as session:
        async with session.get(url, timeout=timeout) as resp:
            return await resp.json()


async def write_article(source, article, engine):
    async with engine.acquire() as conn:
        dic = dict(title=article['title'].encode('utf-8'),
                   aid=sha256(article['url'].encode('utf8')).hexdigest(),
                   created_at=datetime.now(),
                   source=source)

        # i don't like this
        try:
            await conn.execute('BEGIN')
            await conn.execute(article_model.insert().values(**dic))
            await conn.execute('COMMIT')
        except IntegrityError:
            return False
    return True


async def run_task(source, engine):
    try:
        resp = await get_articles(source)
    except TimeoutError:
        return None
    if resp['status'] == 'error':
        return None
    articles = [article for article in resp['articles']]
    tasks = [await write_article(source, article, engine)
             for article in articles]
    counted = Counter(tasks)
    ok, wrong = counted[True], counted[False]
    return ok, wrong


@inject_engine
async def main(engine):
    sources = await get_sources()

    tasks = [ensure_future(run_task(source, engine))
             for source in sources]
    result = await gather(*tasks)
    new = sum([x[0] for x in result if x is not None])
    old = sum([x[1] for x in result if x is not None])
    errors = len([x for x in result if x is None])
    return new, old, errors, len(sources)


def log(new, old, errors, len_sources):
    articles = new + old
    print(f'{len_sources} sources and {articles} were processed')  # noqa
    if new:
        print(f'{new} new articles')
    if errors:
        print(f'There were {errors} errors')
    print('')


async def da_loop():
    while True:
        print(f'{datetime.now()} start')
        result = await main()
        log(*result)
        await aio_sleep(SLEEPING_TIME)

if __name__ == "__main__":
    loop = get_event_loop()
    loop.run_until_complete(da_loop())
