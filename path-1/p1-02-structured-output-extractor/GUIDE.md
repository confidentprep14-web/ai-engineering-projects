# Build guide: Structured Output Extractor

## What you're building and why it matters

Every production LLM pipeline eventually needs to produce structured data — not
freeform text, but a specific object with typed fields. A hiring tool needs JSON
with a job title field, not a paragraph describing the title. A meeting summariser
needs a list of action items, not prose. Getting reliable structured output from
LLMs is harder than it looks: the model might return JSON wrapped in a markdown
code fence, might hallucinate extra fields, or might omit required ones. This
project teaches the retry pattern that every production AI application uses.

## The decision that matters in this build

**Where to put the schema in the prompt.** You have two options: inject the raw
Pydantic JSON schema (verbose, exact), or describe the fields in natural language
(compact, ambiguous). Use the JSON schema. LLMs parse it reliably because it is
the same format used in function calling / tool definitions, which they are trained
on heavily. Natural-language field descriptions lead to more hallucinated extras
and mistyped field names.

## What will break

**Code fences appear even when you say not to.** Saying "return only valid JSON"
in the system prompt reduces fences but does not eliminate them. Always strip
fences before parsing. The `strip_json_fences()` function is not optional.

**Retry prompts must include the error.** If you retry without telling the LLM
what went wrong, it returns the same broken output. Inject the exact error message:
"Previous attempt returned invalid JSON: ValidationError — field 'required_skills'
is missing. Fix it and return valid JSON only."

**Ollama models hallucinate extra fields.** Smaller local models often add fields
not in your schema. Pydantic's `model_validate_json()` will reject them by default
with `extra="forbid"`. This project sets `model_config = ConfigDict(extra="ignore")`
on every schema so an extra hallucinated field does not blow up validation —
only missing or mistyped required fields trigger a retry.

## How to talk about this in an interview

"I built an extraction pipeline where the LLM output is treated as untrusted input.
Every response is validated against a Pydantic schema, and if it fails — whether
due to a missing field or a JSON syntax error — the error is injected into the next
prompt. Across a batch run, my retry logic kept extraction failures near zero with
a max of 3 attempts per document, and I logged the average attempts per document
as the metric that tells me whether the prompt or schema needs tightening."
