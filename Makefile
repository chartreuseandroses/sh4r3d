.PHONY: deploy

deploy:
	cd terraform && terraform init -upgrade && terraform apply
