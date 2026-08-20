# Production environment configuration
# Copy this to terraform.tfvars and fill in the values

environment = "prod"
region      = "ap-south-1"
domain      = "theekkar.in"

# Database password (min 16 chars, mix of upper/lower/numbers/symbols)
db_password = "CHANGE_ME_Strong_P@ssw0rd!"

# JWT secret (min 32 chars, random string)
jwt_secret = "CHANGE_ME_at_least_32_characters_random_string_here"

# AI API key (optional - set to null if not using external LLM)
ai_api_key = null
