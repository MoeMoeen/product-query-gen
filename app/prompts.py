from typing import Dict, Any, Set

# Buckets we currently support. Keep in sync with README and validators.
BUCKETS: Set[str] = {
	"price",
	"occasion",
	"material",
	"fit",
	"brand",
	"rating",
}

def valid_bucket_or_misc(value: str) -> str:
	v = value.lower().strip()
	return v if v in BUCKETS or v == "misc" else "misc"


def system_prompt() -> str:
	return (
		"You are a helpful assistant that generates human-like e-commerce search queries. "
		"Produce a diverse mix of short keyword-style queries and natural language queries. "
		"Queries must be relevant to the given product and reflect realistic user behavior."
	)


def user_prompt_for_product(product: Dict[str, Any], per_bucket: int = 2) -> str:
	"""
	Build a compact instruction asking the model to return JSON with queries
	grouped by bucket and labeled by style.
	"""
	# Only include fields that are present to keep prompt concise
	parts = [
		f"id: {product.get('id')}",
		f"title: {product.get('title')}",
	]
	if product.get("description"):
		parts.append(f"description: {product['description']}")
	if product.get("price") is not None:
		parts.append(f"price: {product['price']}")
	if product.get("material"):
		parts.append(f"material: {product['material']}")
	if product.get("size"):
		parts.append(f"size: {product['size']}")
	if product.get("rating") is not None:
		parts.append(f"rating: {product['rating']}")

	product_block = "\n".join(parts)

	buckets_str = ", ".join(sorted(BUCKETS))

	return (
		"Given the product details below, generate realistic user search queries.\n"
		f"Product:\n{product_block}\n\n"
		f"Buckets: {buckets_str}. For each bucket that applies, generate up to {per_bucket} queries,\n"
		"balancing short keyword-style and natural-language styles.\n"
		"Output strictly in minified JSON with this structure: \n"
		"{\n"
		"  \"queries\": [\n"
		"    {\n"
		"      \"text\": \"string\",\n"
		"      \"style\": \"short\" | \"natural\",\n"
		"      \"bucket\": \"price|occasion|material|fit|brand|rating\"\n"
		"    }\n"
		"  ]\n"
		"}\n"
		"Use only fields present in the product. No explanations or extra keys."
	)

