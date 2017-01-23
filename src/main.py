from asyncio import get_event_loop, ensure_future, wait
from concurrent.futures import TimeoutError
from datetime import datetime
from hashlib import sha256
from os import environ as env

from aiohttp import ClientSession

from aiomysql.sa import create_engine
from pymysql.err import IntegrityError
from models import article as article_model

db = {
    'user': 'user',
    'password': 'password',
    'host': 'mysql',
    'db': 'news',
}


def inject_engine(fnx):
    async def _wrapper(*args, **kwargs):
        engine = await create_engine(loop=get_event_loop(), **db)
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
    query_string = f'?source={source}&apiKey={api_key}'
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
            await conn.execute(article_model.insert().values(**dic))
            await conn.execute('COMMIT')
        except IntegrityError:
            pass
    return True


async def run_task(source, engine):
    try:
        resp = await get_articles(source)
    except TimeoutError:
        return False
    if resp['status'] == 'error':
        return False
    articles = [article for article in resp['articles']]
    tasks = [await write_article(source, article, engine)
             for article in articles]
    return all(tasks)


@inject_engine
async def main(engine):
    sources = await get_sources()
    len_sources = len(sources)

    print(f'{len_sources} sources to process')

    tasks = [ensure_future(run_task(source, engine))
             for source in sources]
    results, _ = await wait(tasks)

    if all([result.result() for result in results]):
        print(f'All {len_sources} tasks were correctly processed')
    else:
        print('Some tasks were not correctly processed')


if __name__ == "__main__":
    loop = get_event_loop()
    loop.run_until_complete(main())
