import os

import instructor
import logfire
import openai
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def execute_chat_completion(
    system_message: str,
    query: str,
    model: str = "gpt-4o",
    reasoning_effort=None,
    response_model=None,
    max_retries: int = 0,
    stream: bool = False,
    max_tokens: int = 8000,
):

    client = OpenAI(max_retries=2)
    logfire.instrument_openai(client)
    client = instructor.from_openai(client)
    try:
        message_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": query},
            ],
            "max_retries": max_retries,
            "stream": stream,
            # "max_tokens": max_tokens,
            "response_model": response_model,
        }

        if model == "o3-mini" and reasoning_effort is not None:
            message_data["reasoning_effort"] = reasoning_effort

        if stream and response_model is not None:
            response = client.chat.completions.create_partial(**message_data)
            error = False
        else:
            response = client.chat.completions.create(**message_data)
            error = False

    except openai.BadRequestError:
        error = True
        logfire.exception("Invalid request to OpenAI API. See traceback:")
        error_message = (
            "Something went wrong while connecting with OpenAI, try again soon!"
        )
        return error_message, error

    except openai.RateLimitError:
        error = True
        logfire.exception("RateLimit error from OpenAI. See traceback:")
        error_message = "OpenAI servers seem to be overloaded, try again later!"
        return error_message, error

    except Exception as e:
        error = True
        logfire.exception(
            "Some kind of error happened trying to generate the response. See traceback:"
        )
        error_message = f"Something went wrong with connecting with the LLM API: {e}"
        return error_message, error

    if stream is True and response_model is None:

        def answer_generator():
            for chunk in response:
                token = chunk.choices[0].delta.content
                token = "" if token is None else token

                yield token

        return answer_generator(), error

    else:
        return response, error
