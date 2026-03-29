IMAGE=ghcr.io/gohugoio/hugo:v0.157.0

SITE=/site
PORT=1313

all: build

## Initialize Hugo module (run once)
init:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	mod init github.com/small-atelier/studio-m

## Download modules / themes
modules: 
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	mod tidy

## Update modules/themes
update-modules:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	mod get -u


## Build static site
build:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	--minify

## Run development server
serve:
	docker run --rm \
	-p $(PORT):1313 \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	server \
	--bind 0.0.0.0 \
	--port 1313 \
	--baseURL http://localhost:1313/ \
	--disableFastRender \
	--buildDrafts \
	--buildFuture

new-post:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	new content/posts/$(name).md

new-project:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	new content/projects/$(name)/index.md


## Create new content
## Example: make new type=posts name=my-post
new:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	new content/$(type)/$(name).md

## Create new project bundle (better for images)
## Example: make new-project name=ork-killteam
new-project:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	new content/projects/$(name)/index.md

## Clean generated files
clean:
	rm -rf public resources

## Show available commands
help:
	@echo ""
	@echo "Studio M Hugo Makefile"
	@echo ""
	@echo "make init                Initialize Hugo module"
	@echo "make modules             Download theme/modules"
	@echo "make update-modules      Update modules"
	@echo "make build               Build static site"
	@echo "make serve               Start development server"
	@echo ""
	@echo "Content creation:"
	@echo "make new type=posts name=my-post"
	@echo "make new type=notes name=my-note"
	@echo "make new type=inventory name=my-unit"
	@echo "make new-project name=my-project"
	@echo ""