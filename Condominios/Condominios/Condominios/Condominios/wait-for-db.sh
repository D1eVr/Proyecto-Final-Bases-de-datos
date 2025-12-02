#!/bin/sh
# wait-for-db.sh

HOST="db"
PORT="3306"

echo "Esperando a que $HOST:$PORT esté disponible..."

# Espera a que MySQL abra el puerto
while ! nc -z $HOST $PORT; do
  sleep 0.5
done

echo "Puerto abierto. Esperando 3 segundos adicionales para la inicialización..."
sleep 3

echo "Base de datos lista. Ejecutando el comando..."
exec "$@"
