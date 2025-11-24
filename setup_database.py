import pymysql

# MySQL connection settings
connection = pymysql.connect(
    host="127.0.0.1",   # or "localhost"
    user="root",        # your MySQL username
    password="",        # leave blank if you have no password
    database="2playerz" # your database name
)

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE();")
        db = cursor.fetchone()
        print("Connected to:", db)

        # Example query
        cursor.execute("SHOW TABLES;")
        for table in cursor.fetchall():
            print("Table:", table[0])

finally:
    connection.close()



