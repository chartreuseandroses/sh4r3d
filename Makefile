.PHONY: deploy

deploy:
	cd terraform && terraform init -upgrade && terraform apply
	@DIST_ID=$$(cd terraform && terraform output -raw cloudfront_distribution_id) && \
	echo "Invalidating CloudFront cache ($$DIST_ID)..." && \
	aws cloudfront create-invalidation --distribution-id $$DIST_ID --paths "/*"
