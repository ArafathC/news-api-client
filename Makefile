clean:
	docker-compose down -v --remove-orphans

create-db:
	docker-compose run --rm news python src/create_db.py

run:
	docker-compose run --rm news python src/main.py

run-mysql:
	docker-compose up mysql -d

sql:
	docker-compose run --rm mysql mysql -h mysql -u user --password=password news
