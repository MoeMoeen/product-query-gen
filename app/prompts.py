from typing import Dict, Any, Set
from math import ceil

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
		"Each query must be written so that THIS product would be the correct or best search result.\n\n"
		"Two styles:\n"
		"- 'short': compact keyword phrases (e.g., 'red silk dress size M').\n"
		"- 'natural': full sentences or questions as if chatting with a sales assistant "
		"(e.g., 'Do you have a red silk dress in size M under $200?').\n\n"
		"Rules:\n"
		"1) Every query must be discriminative enough that the correct answer is the given product.\n"
		"2) Natural queries must be complete sentences with a subject and a verb.\n"
		"3) Include a mix of short and natural queries."
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

	# If price present, compute simple budget hints within ±10% and round up to nearest 10 for upper bound
	budget_hints = ""
	price_val = product.get("price")
	if isinstance(price_val, (int, float)) and price_val > 0:
		around = int(round(price_val / 10.0) * 10)
		upper = int(ceil(price_val * 1.1 / 10.0) * 10)
		# Ensure upper >= around
		if upper < around:
			upper = around
		budget_hints = (
			f"Budget hints (use exactly as phrased; stay within ±10% of price): 'around ${around}', 'under ${upper}', 'below ${upper}'.\n"
		)

	few_shot = (
		"Examples (contrastive):\n"
		"Example 1\n"
		"Product:\n"
		"title: Red Silk Dress\n"
		"price: 120\n"
		"material: Silk\n"
		"occasion: Wedding\n\n"
		"Bad natural (don't do):\n"
		"- \"red silk dress wedding\"\n"
		"- \"silk dress for wedding\"\n\n"
		"Good natural:\n"
		"- \"Do you have a red silk dress I could wear to a wedding?\"\n"
		"- \"I'm looking for a silk dress under $150—any recommendations?\"\n\n"
		"Short:\n"
		"- \"red silk dress\"\n"
		"- \"silk wedding dress\"\n\n"
		"Example 2\n"
		"Product:\n"
		"title: Men's Black Leather Jacket\n"
		"description: Slim fit biker jacket\n"
		"material: Leather\n"
		"rating: 4.7\n\n"
		"Good natural:\n"
		"- \"I want a slim-fit black leather jacket—what would you suggest?\"\n"
		"- \"Could you show me men's leather biker jackets with great reviews?\"\n\n"
		"Short:\n"
		"- \"men black leather jacket\"\n"
		"- \"slim fit biker jacket\"\n\n"
	)

	instructions = (
		"Task: Generate 6–10 queries; roughly 40% short and 60% natural. Include at least one natural query.\n"
		"Critical requirement: Each query must be written so that THIS product would be the correct or best match if a search engine were used. "
		"Do not generate generic advice or information-seeking questions (e.g., 'what is the best...', 'best occasions...').\n"
		f"Buckets to consider: {buckets_str}. If a field is present, include at least one query for that bucket (e.g., price→price, material→material).\n"
		"Spread queries across available buckets. Cover at least min(available, 4) distinct buckets. Limit each bucket to ≤2 queries.\n\n"
		"Compliance checklist (apply silently before output):\n"
		"- Each natural query contains a pronoun (I/you/my/your/we) or ends with '?'.\n"
		"- Each natural query includes at least one auxiliary/modal verb (is/are/am/do/can/could/would).\n"
		"- Natural queries should read like the user is trying to buy or find this exact product (e.g., 'I'm looking for', 'Do you have', 'Can I get').\n"
		"- Natural queries: 8–20 words; include 1–2 longer ones (16–24 words) combining at least two attributes (e.g., size + material, price + occasion).\n"
		"- Short queries contain no punctuation and avoid stopwords (the, a, for, with).\n"
		"- Avoid generic/open-ended questions that do not point to this specific product.\n\n"
		+ budget_hints +
		"Process: First draft 12–14 candidate queries internally. Then SELECT 6–10 that best satisfy the bucket diversity, bucket cap (≤2 per bucket), and the requirement to include 1–2 longer natural queries.\n"
		"Before returning JSON, VALIDATE the final selection against all checklist items. If any condition fails, FIX the queries and re-validate. Return only the final JSON.\n\n"
		"Return a single minified JSON object exactly in this shape (no comments, no markdown, no extra keys, no trailing commas):\n"
		"{\"queries\":[{\"text\":\"string\",\"style\":\"short|natural\",\"bucket\":\"price|occasion|material|fit|brand|rating\"}]}\n"
	)

	return (
		"Generate realistic user queries as instructed.\n\n"
		+ few_shot
		+ "Current product:\n"
		+ product_block
		+ "\n\n"
		+ instructions
		+ "Use only fields present in the product."
	)


def self_check_prompt(product: Dict[str, Any], first_pass_json_minified: str) -> str:
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

	return (
		"You are validating and refining previously generated queries so that they meet all constraints.\n"
		"Current product:\n" + product_block + "\n\n"
		"First-pass JSON (minified):\n" + first_pass_json_minified + "\n\n"
		"Goal: SELECT 6–10 queries that satisfy ALL of the following before returning JSON:\n"
		"- Discriminative: each query should retrieve THIS product.\n"
		"- Bucket diversity: cover ≥4 distinct buckets when available; cap each bucket at ≤2 queries.\n"
		"- Natural richness: include ≥1 natural query between 16–24 words combining at least two attributes (e.g., size + material, price + occasion).\n"
		"- Price normalization: if price is present, keep budget phrasing within ±10% and prefer provided budget hints if any.\n"
		"- Style rules: short queries are ≤5 tokens, no punctuation, avoid stopwords; natural queries are full sentences or questions.\n\n"
		"If constraints are not met, REWRITE as few queries as necessary to comply (minimal edits).\n"
		"Return the final selection ONLY as minified JSON of shape:\n"
		"{\"queries\":[{\"text\":\"string\",\"style\":\"short|natural\",\"bucket\":\"price|occasion|material|fit|brand|rating\"}]}\n"
		"Do not include narration, comments, or extra keys."
	)

