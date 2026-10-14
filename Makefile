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

## Run development server (local Hugo — instant reload)
serve:
	hugo server \
		--bind 0.0.0.0 \
		--port $(PORT) \
		--baseURL http://localhost:$(PORT)/ \
		--disableFastRender \
		--buildDrafts \
		--buildFuture

## Run development server via Docker (no auto-reload on macOS)
docker-serve:
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

new-printable:
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	new content/printables/$(name)/index.md

## Create new army section (with gallery folder)
## Example: make new-army name=ork-killteam
new-army:
	@if [ -z "$(name)" ]; then \
		echo "Error: You must specify an army name, e.g. make new-army name=ork-killteam"; \
		exit 1; \
	fi
	@mkdir -p content/armies/$(name)/gallery
	docker run --rm \
	-v $(PWD):$(SITE) \
	-w $(SITE) \
	$(IMAGE) \
	new content/armies/$(name)/_index.md

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
	@echo "make new-army name=my-army"
	@echo "make new-printable name=my-printable"
	@echo ""

# batch add initial backlog of armies ...
armys:
	@for name in $(subst ',', ' ', $(names)); do \
		echo "Creating army $$name..."; \
		$(MAKE) new-army name=$$name; \
	done