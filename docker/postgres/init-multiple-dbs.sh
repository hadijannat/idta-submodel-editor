#!/bin/bash
# PostgreSQL initialization script for creating multiple databases
# Used by the dataspace profile to create separate DBs for EDC and DTR

set -e
set -u

function create_user_and_database() {
    local database=$1
    local user=$2
    local password=$3
    echo "Creating user and database '$database'"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        CREATE USER $user WITH PASSWORD '$password';
        CREATE DATABASE $database;
        GRANT ALL PRIVILEGES ON DATABASE $database TO $user;
        \c $database
        GRANT ALL ON SCHEMA public TO $user;
EOSQL
}

# Check if POSTGRES_MULTIPLE_DATABASES is set
if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "Multiple database creation requested: $POSTGRES_MULTIPLE_DATABASES"

    # Create EDC database and user
    create_user_and_database "edc" "edc" "edc_password"

    # Create DTR database and user
    create_user_and_database "dtr" "dtr" "dtr_password"

    echo "Multiple databases created"
fi
