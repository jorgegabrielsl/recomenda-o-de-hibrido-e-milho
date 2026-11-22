from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv(override=True)

host = os.getenv('HOST')
user = os.getenv('USER')
password = os.getenv('PASSWORD')
port = os.getenv('PORT')
sid = os.getenv('SID')


def conexao_pgsql():
    engine = create_engine(f"postgresql://{user}:{password}@{host}:{port}/{sid}")
    return engine
