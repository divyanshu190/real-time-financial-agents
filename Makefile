.PHONY: install train demo test docker
install:
	pip install -r requirements.txt
train:
	PYTHONPATH=src python -m fa.ml
demo:
	PYTHONPATH=src python -m fa.run --speed 200
test:
	PYTHONPATH=src python -m pytest -q tests
docker:
	docker build -t fa-pathway . && docker run --rm fa-pathway
