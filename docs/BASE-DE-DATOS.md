# Base de datos — cómo levantarla

El proyecto necesita **cualquier MySQL 8 o MariaDB 10.4+**. No está atado a
XAMPP: el puerto por defecto es el estándar **3306** y se cambia en `.env`.

`start.py` crea la base `dataops` y las 20 tablas automáticamente a partir de
`db/schema.sql`. No hay que crear nada a mano.

## Opción 1 — MySQL/MariaDB que ya tienes (recomendada)

Si ya tienes un servidor MySQL o MariaDB corriendo:

1. Copia la plantilla y ajústala:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Edita `.env` con host, puerto, usuario y clave.
3. Listo. `start.py` crea la base y las tablas.

Verifica que responde:

```powershell
mysql -h 127.0.0.1 -P 3306 -u root -p -e "SELECT VERSION();"
```

## Opción 2 — XAMPP

1. Abre *XAMPP Control Panel* → **Start** en MySQL.
2. MySQL de XAMPP escucha en el puerto **3306** por defecto.
3. Copia `.env.example` como `.env`. Si tu XAMPP usa otro puerto, ajústalo.

Si MySQL de XAMPP pide clave (no es lo normal), créale un usuario:

```sql
CREATE USER 'dataops'@'127.0.0.1' IDENTIFIED BY 'tu_clave_aqui';
GRANT ALL PRIVILEGES ON dataops.* TO 'dataops'@'127.0.0.1';
FLUSH PRIVILEGES;
```

y ponlo en `.env`.

## Opción 3 — MariaDB/MySQL instalado aparte

1. Instálalo (Windows: [MariaDB Installer](https://mariadb.org/download/),
   Linux: `sudo apt install mariadb-server`).
2. Inicia el servicio:
   - Windows: `net start MySQL80` (o desde *Servicios*)
   - Linux: `sudo systemctl start mariadb`
3. Copia `.env.example` como `.env` (el puerto 3306 ya viene bien).

## Opción 4 — Docker (un solo comando)

```powershell
docker run -d --name dataops-db -p 3306:3306 `
  -e MYSQL_ROOT_PASSWORD=clave -e MYSQL_DATABASE=dataops `
  mysql:8
```

Luego en `.env`: `DATAOPS_DB_PASSWORD=clave`.

## Nota sobre Windows: `--console`

Si arrancas `mysqld.exe` a mano **sin** `--console`, el proceso se cierra
solo al terminar la consola. Arranca siempre con esa opción:

```
C:\xampp\mysql\bin\mysqld.exe --datadir=<carpeta> --port=3306 --console
```

## Usuario con permisos (recomendado)

Para no usar `root`, crea un usuario propio:

```sql
CREATE USER 'dataops'@'127.0.0.1' IDENTIFIED BY 'tu_clave_aqui';
GRANT ALL PRIVILEGES ON dataops.* TO 'dataops'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Y ponlo en `.env`. **Ojo:** para correr las pruebas, el usuario necesita
permiso también sobre la base de pruebas:

```sql
GRANT ALL PRIVILEGES ON `dataops_test%`.* TO 'dataops'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `Can't connect to MySQL server` | El servidor no está arriba | Inícialo y revisa el puerto en `.env` |
| `Access denied for user` | Credenciales incorrectas | Revisa `DATAOPS_DB_USER` / `DATAOPS_DB_PASSWORD` |
| `Unknown database 'dataops'` | La base no se creó | `start.py` la crea; corre `python start.py` |
| `Table 'dataops_test.x' doesn't exist` | Faltan permisos para pruebas | Grant sobre `dataops_test%` |
