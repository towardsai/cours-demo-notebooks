import logfire
from pydantic import BaseModel, Field, ValidationError, model_validator

system_message_validation = """You are a world-class data analyst. You can provide guidance and answer questions, but first, you need to validate if the query is about data analysis, more spcifically in the context of Online Retail II data, a dataset that contains all the transactions occurring for a UK-based and registered, non-store online retail between 01/12/2009 and 09/12/2011.The company mainly sells unique all-occasion gift-ware. Many customers of the company are wholesalers."""


class QueryValidation(BaseModel):
    """
    Validate the user query. Ensure the query is related to data analysis.
    """

    chain_of_thought: str = Field(
        description="Is the user query related to data analysis? Think step-by-step. Write down your chain of thought here.",
    )
    is_valid: bool = Field(
        description="Based on the previous reasoning, answer with True if the query is related to data analysis. Answer False otherwise.",
    )
    reason: str = Field(
        description="Explain why the query is valid or not. What are the keywords that make it valid?",
    )


system_message_plan = """You are a world-class task-planning algorithm and developer capable of breaking down user questions into a solvable snippet of Python code.
You have a Pandas dataframe at your disposal. Remember that some values might be `None` or `NaN`.
The name of the dataframe is `df` and its case insensitive.
Remember: You cannot subset columns with a tuple with more than one element. Use a list instead.

Keep in mind the following warning:
<string>:10: SettingWithCopyWarning: 
A value is trying to be set on a copy of a slice from a DataFrame.
Try using .loc[row_indexer,col_indexer] = value instead
See the caveats in the documentation: https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#returning-a-view-versus-a-copy


Here are the headings and a brief description for each column:
InvoiceNo: Invoice number. Nominal. A 6-digit integral number uniquely assigned to each transaction. IMPORTANT! >If this code starts with the letter 'c', it indicates a cancellation.<
StockCode: Product (item) code. Nominal. A 5-digit integral number uniquely assigned to each distinct product.
Description: Product (item) name. Nominal. (some values may be missing when products lack formal descriptions but can still be identified by StockCode).
Quantity: The quantities of each product (item) per transaction. Numeric. (may include negative values)
InvoiceDate: Invice date and time. Numeric. The day and time when a transaction was generated.
UnitPrice: Unit price. Numeric. Product price per unit in sterling (Â£). (may include negative values)
CustomerID: Customer number. Nominal. A 5-digit integral number uniquely assigned to each customer.
Country: Country name. Nominal. The name of the country where a customer resides.


Here are more details created with df.info():

<class 'pandas.core.frame.DataFrame'>
RangeIndex: 525461 entries, 0 to 525460
Data columns (total 8 columns):
 #   Column       Non-Null Count   Dtype         
---  ------       --------------   -----         
 0   Invoice      525461 non-null  object        
 1   StockCode    525461 non-null  object        
 2   Description  522533 non-null  object        
 3   Quantity     525461 non-null  int64         
 4   InvoiceDate  525461 non-null  datetime64[ns]
 5   Price        525461 non-null  float64       
 6   Customer ID  417534 non-null  float64       
 7   Country      525461 non-null  object        
dtypes: datetime64[ns](1), float64(2), int64(1), object(4)
memory usage: 32.1+ MB

Note on empty values:
- Description: ~2,928 missing values (0.6%) - Products may still be identifiable by StockCode
- Customer ID: ~107,927 missing values (20.5%) - Likely represent guest purchases without account registration
- All other columns have complete data as they are essential for transaction tracking

Here are some rules to follow:
- You must use print statements to display relevant execution results.
- When computing over numerical values, make sure not to round the values.
"""


class TaskPlan(BaseModel):
    """- Generates Python code to be executed over a Pandas dataframe. Avoid including import statements.
    - If the query involves filtering a semantic column, provide variations of this phrase or similar terms that could mean the same thing.
    - You must use a print statement at the end to display the output but only print the relevant columns if necessary.
    """

    user_query: str = Field(
        description="The user query that you need to answer. This is the question you need to answer using the pandas dataframe.",
    )
    chain_of_thought: str = Field(
        description="How will you answer the user_query using the pandas dataframe. Think step-by-step. Write down your chain of thought and reasoning. What will you print as a result? Will the code be free of bugs?",
    )
    code_to_execute: str = Field(
        description="Based on the previous reasoning, write bug-free code for the `python_repl` tool. Make sure to write code without bugs. Avoid import statements. Print the relevant columns.",
    )
    is_code_bug_free: bool = Field(
        description="Reflect on the previously generated code, answer with True if the code is safe, will run without issues and answers the user query. Answer False otherwise. Does it have extra indentations?",
    )
    result: str = Field(
        default="",
        description="The result of the code execution. If the code has not been executed yet, leave this field empty.",
    )

    @model_validator(mode="after")
    def validate_and_execute_code(self):

        result, error_occurred, error_message = self.execute_generated_code()
        if error_occurred:
            self.is_code_bug_free = False
            logfire.error(f"An error occurred: {error_message}")
            raise ValueError(f"An error occurred: {error_message}")

        logfire.info(f"Code execution ran successfully")
        self.result = result
        return self

    def execute_generated_code(self):
        import io
        from contextlib import redirect_stdout

        globals_dict = {}

        import_and_load = """import pandas as pd
import numpy as np
pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', 30)
pd.set_option('display.max_colwidth', 400)
# Load the dataframe
df = pd.read_excel("data/online_retail_II.xlsx", sheet_name="Year 2009-2010")
"""
        code: str = import_and_load + self.code_to_execute
        logfire.info(f"Code that will be executed: \n\n{code}\n")
        with logfire.span(f"Running code execution...\n"):
            output_buffer = io.StringIO()
            error_occurred = False
            error_message = ""

            try:
                with redirect_stdout(output_buffer):
                    exec(code, globals_dict)
                result = output_buffer.getvalue()
            except Exception as e:
                error_occurred = True
                error_message = str(e)
                result = f"Error: {error_message}"

            return result, error_occurred, error_message


# -----------------------------------------------------------------------------------------------------

system_message_synthesiser = """- You are a world-class data analyst, your task is to answer the user query in a way that is helpful and complete.  
- The answer must include all the information you have at your disposal.
- At your disposal, you have the results of executed Python code.
- The executed code was used a Python Pandas Dataframe containing online retrail data.
- Users do not see the code or its output. They only see your answer. Use the information to generate a complete and helpful reply.
- Use Markdown to format your answer. Use headings, bold, italics, and lists to make your answer clear and easy to read.
- Provide the user with all the information; do not cut down your answer.
- If the executed code result is empty, state that no information is available in the database.
"""


synthesiser_prompt = """<user_query>
{query}
</user_query>
  
<executed_code>
{executed_code}
</executed_code>
  
<exec_tool_output>
{result}
</exec_tool_output>
  
<instructions>
You are a data analyst.
Give a complete answer to the user question.
Avoid short answers, statements like '...and more.'
</instructions>
"""
