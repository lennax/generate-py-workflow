export PATH := $(HOME)/go/bin:$(PATH)
.PHONY: create_venv test

create_venv:
	python3 -m venv .venv
	./.venv/bin/python3 -m pip install --upgrade pip
	./.venv/bin/python3 -m pip install -r requirements.txt
	go install github.com/rhysd/actionlint/cmd/actionlint@latest

test:
	./.venv/bin/python3 generate_reusable_workflow.py example_script.py
	actionlint generated_workflow.yml
	diff generated_workflow.yml reference_workflow.yml
