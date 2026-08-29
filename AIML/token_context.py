import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")

# Assume a small context window for demonstration purposes
CONTEXT_WINDOW_LIMIT = 100  # tokens (artificially small, to hit the limit quickly)

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

# --- Part 1: Tokenization demo ---
print("=" * 50)
print("PART 1: How text becomes tokens")
print("=" * 50)

samples = [
    "Hi",
    "Hi, my name is Alex",
    "Supercalifragilisticexpialidocious",
]

for text in samples:
    tokens = encoding.encode(text)
    print(f"\nText: {text!r}")
    print(f"Token count: {len(tokens)}")
    print(f"Tokens: {[encoding.decode([t]) for t in tokens]}")

# --- Part 2: Context window demo ---
print("\n" + "=" * 50)
print("PART 2: Filling up a context window")
print("=" * 50)
print(f"(Simulated limit: {CONTEXT_WINDOW_LIMIT} tokens)\n")

conversation = []
messages = [
    "Hi, my name is Alex.",
    "I live in Bangalore.",
    "I work as a software engineer.",
    "My favorite programming language is Python.",
    "I studied at a university in Delhi.",
    "I have a dog named Rocky.",
    "Let me tell you a long story about my weekend trip to the mountains where we hiked for six hours and saw beautiful waterfalls and wildlife along the trail.",
    "I enjoy hiking on weekends.",
]

print("\n" + "=" * 50)
print("PART 3: Trimming to stay within the limit")
print("=" * 50)

MAX_MESSAGES_KEPT = 4  # similar to MAX_HISTORY_TURNS in memory.py

trimmed_conversation = []
for msg in messages:
    trimmed_conversation.append(msg)
    # Keep only the last N messages, same strategy as memory.py's _trim()
    trimmed_conversation = trimmed_conversation[-MAX_MESSAGES_KEPT:]

    full_text = " ".join(trimmed_conversation)
    tokens = count_tokens(full_text)
    print(f"Added: {msg!r}")
    print(f"Trimmed conversation tokens: {tokens} (kept last {len(trimmed_conversation)} messages)\n")

total_tokens = 0
for msg in messages:
    conversation.append(msg)
    full_text = " ".join(conversation)
    total_tokens = count_tokens(full_text)

    print(f"Added: {msg!r}")
    print(f"Total conversation tokens so far: {total_tokens}")

    if total_tokens > CONTEXT_WINDOW_LIMIT:
        print(f"\nCONTEXT WINDOW EXCEEDED at {total_tokens} tokens!")
        print("Oldest messages would need to be dropped or summarized to continue.\n")
        break
    print()
