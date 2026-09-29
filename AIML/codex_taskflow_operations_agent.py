import os

from groq import Groq


client = Groq(
    api_key=os.environ["GROQ_API_KEY"]
)


SYSTEM_INSTRUCTIONS = """
You are the TaskFlow Operations Analyst.

Your responsibility is to inspect TaskFlow operational information
without modifying application source code or performing privileged
operations.

You may:

- summarize TaskFlow operational information;
- review task state;
- review migration state;
- recommend next steps.

You must not:

- directly modify taskflow.db;
- execute migrations;
- delete tasks;
- edit repository source code;
- claim that an operation was performed unless a tool actually
  performed it.

Return results using this structure:

1. Request
2. Evidence
3. Findings
4. Actions Not Performed
5. Recommended Next Step
"""


def run_agent(user_request: str) -> str:
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": user_request,
            },
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    request = """
    Explain your role as the TaskFlow Operations Analyst.

    Describe what you are allowed to do and what operations
    you must not perform.
    """

    print(run_agent(request))
