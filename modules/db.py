# modules/db.py
import mysql.connector

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",   # sesuaikan jika berbeda
        database="depo78"
    )
