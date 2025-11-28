from sqlalchemy import create_engine, inspect

engine = create_engine("sqlite:///../datos/robot_data.db")
insp = inspect(engine)

print("Tablas en la BD:")
print(insp.get_table_names())

for table in insp.get_table_names():
    print(f"\n--- Contenido de {table} ---")
    columns = [col['name'] for col in insp.get_columns(table)]
    print("Columnas:", columns)

    with engine.connect() as conn:
        result = conn.execute(f"SELECT * FROM {table} LIMIT 20")
        for row in result.fetchall():
            print(dict(row))
