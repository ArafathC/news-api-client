from sqlalchemy import create_engine

from models import metadata

engine = create_engine('mysql+pymysql://user:password@mysql/news?charset=utf8')

metadata.create_all(engine)
