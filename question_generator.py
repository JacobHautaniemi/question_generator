import os
import csv
import re
import zipfile
from dotenv import load_dotenv
from groq import Groq
import subprocess

os.environ["GROQ_API_KEY"] = ""

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

# Initialize the Groq client
client = Groq(api_key=api_key)

def generate_questions_groq(num_questions, question_type, student_age, topic):
    question_prompt = (
        f"Generate {num_questions} {'fill-in-the-blank' if question_type else 'multiple-choice'} "
        f"{topic} questions for {student_age} students. Each question should have 4 answers, with one correct answer indicated. "
        "The format should be exactly as follows:\n\n"
        "Question X\n"
        "Question text\n"
        "Answer 1\n"
        "Answer 2\n"
        "Answer 3\n"
        "Answer 4\n"
        "Correct answer: Y\n\n"
        "Replace X with the question number. State the question number as: Question X (bolded). For the correct answer line, replace Y with the answer number only (1/2/3/4) - only state Y as a number. Never state option A/B/C/D or 1/2/3/4 etc, only the text. Use the exact same format, including a new line where specified."
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": question_prompt
            }
        ],
        model="llama3-8b-8192",
    )

    questions_output = chat_completion.choices[0].message.content.strip()
    print("Raw output from GROQ:\n", questions_output)  # Debugging line
    return parse_questions_output(questions_output)

def sanitize_text(text):
    # Remove non-English characters and symbols
    return re.sub(r'[^\x00-\x7F]+', '', text)

def parse_questions_output(output):
    questions = []
    lines = output.split('\n')
    i = 0

    while i < len(lines):
        line = sanitize_text(lines[i].strip())
        if line.startswith('**Question'):
            # Check if there are enough lines remaining for a complete question
            if i + 6 < len(lines):
                question_text = sanitize_text(lines[i + 1].strip())
                answers = []
                for j in range(2, 6):
                    answers.append(sanitize_text(lines[i + j].strip()))
                correct_answer_line = sanitize_text(lines[i + 6].strip())
                if "Correct answer:" in correct_answer_line:
                    correct_answer = correct_answer_line.split(': ')[1]
                else:
                    print(f"Skipping malformed correct answer line: {correct_answer_line}")
                    correct_answer = "Unknown"
                questions.append({
                    'Question #': len(questions) + 1,
                    'Question Text': question_text,
                    'Answer 1': answers[0],
                    'Answer 2': answers[1],
                    'Answer 3': answers[2],
                    'Answer 4': answers[3],
                    'Correct answer': correct_answer
                })
                i += 7
            else:
                print(f"Skipping incomplete question starting at line {i}: {line}")
                break
        else:
            print(f"Skipping malformed question line: {line}")
            i += 1

    print(f"Parsed {len(questions)} questions successfully.")  # Debugging line
    return questions

def export_questions_csv(questions, file_path):
    headers = ['Question #', 'Question Text', 'Answer 1', 'Answer 2', 'Answer 3', 'Answer 4', 'Correct Answer']
    with open(file_path, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for question in questions:
            writer.writerow({
                'Question #': question['Question #'],
                'Question Text': question['Question Text'],
                'Answer 1': question['Answer 1'],
                'Answer 2': question['Answer 2'],
                'Answer 3': question['Answer 3'],
                'Answer 4': question['Answer 4'],
                'Correct Answer': question['Correct answer']
            })

def create_text2qti_input(questions, file_path, topic):
    with open(file_path, 'w') as file:
        file.write(f"Quiz title: {topic}\n")
        file.write("Quiz description: Multiple choice formative quiz\n\n")
        for question in questions:
            file.write(f"{question['Question #']}. {question['Question Text']}\n")
            for i, answer in enumerate(['Answer 1', 'Answer 2', 'Answer 3', 'Answer 4']):
                prefix = "*" if str(i + 1) == question['Correct answer'] else ""
                file.write(f"{prefix}{chr(65+i)}) {question[answer]}\n")
            file.write("\n")

def convert_to_canvas_format(input_path):
    command = f"text2qti \"{input_path}\""
    subprocess.run(command, shell=True, check=True)

# Example usage
if __name__ == "__main__":
    format_choice = input("Enter the format (Blooket/CANVAS): ").strip().lower()
    num_questions = int(input("Enter the number of questions: ").strip())
    question_type = False  # False for multiple-choice (you can modify this based on further user input if needed)
    student_age = input("Enter the student age (e.g., Year 12): ").strip()
    topic = input("Enter the topic: ").strip()

    questions = generate_questions_groq(num_questions, question_type, student_age, topic)

    if format_choice == "blooket":
        csv_path = os.path.join(os.path.expanduser("~"), "Downloads", f"{topic}.csv")
        export_questions_csv(questions, csv_path)
        print(f"Blooket-compatible CSV file has been created at {csv_path}.")
    elif format_choice == "canvas":
        text2qti_input_path = os.path.join(os.path.expanduser("~"), "Downloads", f"{topic}.txt")
        zip_output_path = os.path.join(os.path.expanduser("~"), "Downloads", f"{topic}.zip")
        
        create_text2qti_input(questions, text2qti_input_path, topic)
        convert_to_canvas_format(text2qti_input_path)
        print(f"Canvas-compatible ZIP file has been created at {zip_output_path}.")
    else:
        print("Invalid format choice.")
