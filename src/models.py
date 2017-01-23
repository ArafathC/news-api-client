from sqlalchemy import MetaData, Table, Column, String, DateTime

metadata = MetaData()

article = \
    Table('articles', metadata,
          Column('aid', String(64), primary_key=True),
          Column('title', String(255)),
          Column('source', String(64)),
          Column('created_at', DateTime),
          )
