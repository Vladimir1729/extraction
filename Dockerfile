# Usa una versión más reciente y segura
FROM python:3.12-slim-bookworm

# Instala dependencias del sistema necesarias para pyodbc y ODBC
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    g++ \
    unixodbc-dev \
    unixodbc \
    odbcinst \
    tdsodbc \
    freetds-dev \
    freetds-bin \
    freetds-common \
    && rm -rf /var/lib/apt/lists/*

# Configuración del driver ODBC para SQL Server
RUN echo "[FreeTDS]\n\
Description = FreeTDS Driver\n\
Driver = /usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so\n\
Setup = /usr/lib/x86_64-linux-gnu/odbc/libtdsS.so" >> /etc/odbcinst.ini

# Crea un directorio para la aplicación
WORKDIR /app

# Copia primero los requerimientos para aprovechar caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el archivo principal y cualquier otro archivo necesario
COPY main.py .
# Si tienes más archivos, puedes usar: COPY . .

# Establece el comando para ejecutar la aplicación
CMD ["python", "main.py"]