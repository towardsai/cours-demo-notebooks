import argparse
import json
import logging
import pdb
import time

import logfire
import structured_output_utilities as models
from llm_api_connector import execute_chat_completion
from openai.types.chat import ChatCompletion
from rich.console import Console
from rich.markdown import Markdown

logfire.configure()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Excel RAG Chatbot")
    parser.add_argument("--query", type=str, required=False, help="Question to ask")
    parser.add_argument(
        "--jsonl_file",
        type=str,
        default="exercise_2/test_queries.jsonl",
        help="Path to JSONL file with queries",
    )
    parser.add_argument(
        "--process_jsonl",
        action="store_true",
        help="Process all queries from the JSONL file",
    )
    return parser.parse_args()


def process_query(query):
    """Process a single query and return the generated output."""
    with logfire.span(f"Processing query: {query}"):
        logfire.info(f"Step 1: Generating task plan for query and executing code")
        plan, error = execute_chat_completion(
            system_message=models.system_message_plan,
            query=query,
            model="gpt-4o",
            response_model=models.TaskPlan,
            max_retries=3,
            stream=False,
        )
        if error:
            logfire.error("Error occurred during API call")
            return None

        if not isinstance(plan, models.TaskPlan):
            logfire.error("Could not create TaskPlan")
            return None

        synthesiser_prompt = models.synthesiser_prompt.format(
            query=query,
            executed_code=plan.code_to_execute,
            result=plan.result,
        )

        logfire.info(f"Step 2: Generating final answer")
        response, error = execute_chat_completion(
            system_message=models.system_message_synthesiser,
            query=synthesiser_prompt,
            model="gpt-4o",
            stream=False,
        )
        if error:
            logfire.error("Error occurred during API call")
            return None

        console = Console()

        if isinstance(response, ChatCompletion):
            return str(response.choices[0].message.content)
        else:
            for chunk in response:
                console.print(chunk, end="")
            return None


def process_jsonl_file(file_path):
    """Process all queries in the JSONL file and update the generated_output field."""
    try:
        # Read the JSONL file
        with open(file_path, "r", encoding="utf-8") as file:
            queries = [json.loads(line) for line in file]

        # Process each query and save immediately after each one
        for i, query_obj in enumerate(queries):
            print(f"\n\nProcessing query {i+1}/{len(queries)}: {query_obj['query']}")
            query_obj["generated_output"] = process_query(query_obj["query"])

            # Save the updated file after each query is processed
            with open(file_path, "w", encoding="utf-8") as file:
                for j, q_obj in enumerate(queries):
                    file.write(json.dumps(q_obj, ensure_ascii=False) + "\n")

            print(f"Saved progress after query {i+1}/{len(queries)}")

        print(f"Successfully processed all queries and updated {file_path}")
    except Exception as e:
        logfire.error(f"Error processing JSONL file: {e}")


def main():
    args = parse_arguments()

    if args.process_jsonl:
        logfire.info(f"Running in batch mode with file: {args.jsonl_file}")
        process_jsonl_file(args.jsonl_file)
    else:
        query = args.query
        if not query:
            query = "Quelle est la valeur vie client moyenne?"

        start_time = time.time()
        response = process_query(query)
        end_time = time.time()

        if response:
            console = Console()
            console.print(Markdown(response))

        print("\n\ntime taken for whole process:", end_time - start_time)


if __name__ == "__main__":
    main()
