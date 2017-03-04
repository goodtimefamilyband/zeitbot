# schema.py

#from config import SQLALCHEMY_DATABASE_URI, SQL_DEBUG
SQLALCHEMY_DATABASE_URI = 'sqlite:///zeitbot.db'
SQL_DEBUG = False

#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean

Base = declarative_base()
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=SQL_DEBUG)

Session = sessionmaker(bind=engine)    
        
