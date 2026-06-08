PYTHON_312 := /Users/ricepotato/.local/share/uv/python/cpython-3.12.10-macos-aarch64-none/bin
export PATH := $(PYTHON_312):$(PATH)

.PHONY: build deploy

build:
	sam build

deploy: build
	sam deploy --no-confirm-changeset
