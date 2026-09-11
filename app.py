from flask import Flask, render_template, request,send_from_directory,session,redirect 
from pypdf import PdfReader
from google import genai
import os
import json
import uuid
import sqlite3
from markupsafe import Markup
import markdown
from database import init_db
from datetime import datetime


app = Flask(__name__)

app.secret_key = "learnwise-secret-key"
init_db()

connection = sqlite3.connect("learnwise.db")
cursor = connection.cursor()

cursor.execute(
    "SELECT id FROM students WHERE name = ?",
    ("Student 1",)
)

student = cursor.fetchone()

if student:
    student_id = student[0]
else:
    cursor.execute(
        "INSERT INTO students (name) VALUES (?)",
        ("Student 1",)
    )

    student_id = cursor.lastrowid
    connection.commit()

connection.close()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))




@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    session["student_id"] = student_id
    return render_template("dashboard.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():

    if request.method == "POST":

        pdf_file = request.files.get("pdf_file")

        if not pdf_file or pdf_file.filename == "":
            return "Please select a PDF file."

        os.makedirs("uploads", exist_ok=True)

        pdf_path = "uploads/" + pdf_file.filename

        pdf_file.save(pdf_path)
        connection = sqlite3.connect("learnwise.db")
        cursor = connection.cursor()

        cursor.execute(
    "INSERT INTO study_materials (student_id, filename, created_at) VALUES (?, ?, ?)",(
           session["student_id"],
          pdf_file.filename,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")
     )
       )

        material_id = cursor.lastrowid
        session["material_id"] = material_id
        connection.commit()
        connection.close()

        reader = PdfReader(pdf_path)

        pdf_text = ""

        for page in reader.pages:
            pdf_text += page.extract_text() or ""

        session["pdf_filename"] = pdf_file.filename

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents="""Create a clean, topic-wise summary of the study material for a student.

            For each main topic:
            1. Give the topic name as a clear heading.
            2. Divide the topic into smaller subtopics where appropriate.
            3. Explain each subtopic in clear, simple paragraphs.
            4. Use bullet points only when listing items or key points. Put each bullet point on a separate new line.
            5. Use tables when comparing or categorizing information.
            6. Highlight important terms and exam-relevant facts.
            7. Keep related information together.
            8. Avoid labels such as 'Definition:', 'Examples:', 'Categories:' unless they are genuinely useful.
            9. Do not repeat the same information in different sections.
            10. Do not write an introduction about the document or say that you are analyzing it.
            11. Do not add information that is not present in the study material.
            12. Make the final result look like neatly organized study notes, not an AI report.

            Cover all important topics from the material without unnecessarily shortening the content.

            Study material:

            \n\n""" + pdf_text
        )

        ai_html = markdown.markdown(
            response.text,
            extensions=["tables"]
        )

        os.makedirs("summaries", exist_ok=True)

        with open(
            "summaries/" + pdf_file.filename + ".html",
            "w",
            encoding="utf-8"
        ) as file:
            file.write(ai_html)
        connection = sqlite3.connect("learnwise.db")
        cursor = connection.cursor()

        cursor.execute(
                 "INSERT INTO summaries (material_id, summary) VALUES (?, ?)",
                  (material_id, ai_html)
        )

        connection.commit()
        connection.close()
        return redirect("/upload")

    filename = session.get("pdf_filename")

    return render_template(
        "upload.html",
        filename=filename
    )

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory("uploads", filename)



@app.route("/learn")
def learn():
    pdf_filename = session.get("pdf_filename")
    if not pdf_filename or not os.path.exists(os.path.join("uploads", pdf_filename)):
         return """
    <h2>Please upload a PDF first.</h2>
    <p>Upload your study material to view the summary.</p>
    <a href="/upload">Upload Study Material</a>
          """
    summary_path = os.path.join("summaries", pdf_filename + ".html")

    with open(summary_path, "r", encoding="utf-8") as file:
        ai_html = file.read()

    return render_template(
        "learn.html",
        ai_response=Markup(ai_html)
    )



@app.route("/ask-ai", methods=["GET", "POST"])
def ask_ai():

    pdf_filename = session.get("pdf_filename")
    if not pdf_filename or not os.path.exists(os.path.join("uploads", pdf_filename)):
         return """
    <h2>Please upload a PDF first.</h2>
    <p>Upload your study material before asking AI questions.</p>
    <a href="/upload">Upload Study Material</a>
         """
    pdf_path = os.path.join("uploads", pdf_filename)

    reader = PdfReader(pdf_path)

    pdf_text = ""

    for page in reader.pages:
        pdf_text += page.extract_text() or ""

    ai_answer = None

    if request.method == "POST":

        question = request.form["question"]

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents="""Answer the student's question using only the uploaded study material.

Do not add information that is not present in the study material.

Study material:
""" + pdf_text + """

Student's question:
""" + question
        )
        connection = sqlite3.connect("learnwise.db")
        cursor = connection.cursor()

        cursor.execute(
                 "INSERT INTO ai_questions (material_id, question, answer, created_at) VALUES (?, ?, ?,?)",
                    (
                        session["material_id"],
                            question,
                            response.text,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    )
        )

        connection.commit()
        connection.close()
        ai_answer = Markup(
               markdown.markdown(
               response.text,
               extensions=["tables"]
               )
            )

    return render_template(
        "ask_ai.html",
        ai_answer=ai_answer
    )

@app.route("/quiz", methods=["GET", "POST"])
def quiz():

    pdf_filename = session.get("pdf_filename")

    if not pdf_filename or not os.path.exists(os.path.join("uploads", pdf_filename)):
          return """
    <h2>Please upload a PDF first.</h2>
    <p>Upload your study material to access the quiz.</p>
    <a href="/upload">Upload Study Material</a>
          """

    if request.method == "POST":

        question_count = int(request.form["question_count"])

        print(question_count)

        pdf_path = os.path.join(
            "uploads",
            pdf_filename
        )

        reader = PdfReader(pdf_path)

        pdf_text = ""

        for page in reader.pages:
            pdf_text += page.extract_text() or ""

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"""Create exactly {question_count} multiple-choice questions from the study material.

Return ONLY valid JSON.

Use exactly this format:

[
  {{
    "question": "Question text",
    "options": {{
      "A": "Option A",
      "B": "Option B",
      "C": "Option C",
      "D": "Option D"
    }},
    "answer": "A",
    "topic": "Topic name"
  }}
]

Rules:
- Create exactly {question_count} questions.
- Each question must have exactly 4 options: A, B, C and D.
- Only one option must be correct.
- The answer must contain only A, B, C or D.
- Include the topic for every question.
- Questions must be based only on the uploaded study material.
- Do not add information that is not present in the study material.

Study material:
""" + pdf_text
        )

        questions = json.loads(response.text)

        quiz_id = str(uuid.uuid4())

        os.makedirs("quizzes", exist_ok=True)

        quiz_path = os.path.join(
            "quizzes",
            quiz_id + ".json"
        )

        with open(quiz_path, "w", encoding="utf-8") as file:
            json.dump(questions, file, indent=4)
            student_answers = {}

        
        return render_template(
            "quiz.html",
            questions=questions,
            quiz_id=quiz_id
        )

    return render_template("quiz.html")

@app.route("/submit-quiz", methods=["POST"])
def submit_quiz():
    print("SUBMIT QUIZ ROUTE REACHED")
    quiz_id = request.form["quiz_id"]

    quiz_path = os.path.join(
        "quizzes",
        quiz_id + ".json"
    )

    with open(quiz_path, "r", encoding="utf-8") as file:
        questions = json.load(file)
        student_answers = {}

    for i in range(len(questions)):
        answer = request.form.get(f"q{i + 1}")
        student_answers[i + 1] = answer
       
    correct_count = 0

    for i in range(len(questions)):
        correct_answer = questions[i]["answer"]
        student_answer = student_answers[i + 1]

        if student_answer == correct_answer:
            correct_count += 1
    overall_percentage = (correct_count / len(questions)) * 100
    results = []

    for i in range(len(questions)):

            correct_answer = questions[i]["answer"]
            student_answer = student_answers[i + 1]

            if student_answer == correct_answer:
                   result = "Correct"
            else:
                result = "Wrong"

            results.append({
                 "question": questions[i]["question"],
                 "student_answer": student_answer,
                 "correct_answer": correct_answer,
                  "result": result
           })
    topic_scores = {}

    for i in range(len(questions)):

        topic = questions[i]["topic"]

        if topic not in topic_scores:
            topic_scores[topic] = {
            "correct": 0,
            "total": 0
        }

        topic_scores[topic]["total"] += 1

        if student_answers[i + 1] == questions[i]["answer"]:
             topic_scores[topic]["correct"] += 1
    for topic in topic_scores:

         correct = topic_scores[topic]["correct"]
         total = topic_scores[topic]["total"]

         topic_scores[topic]["percentage"] = (correct / total) * 100

    print("Topic Scores:", topic_scores)
    weak_threshold = 60
    weak_topics = []

    for topic in topic_scores:

          topic_percentage = topic_scores[topic]["percentage"]

          if topic_percentage < weak_threshold:
                 weak_topics.append(topic)
    weak_topic_data = []

    for topic in weak_topics:

            wrong_questions = []

            for i in range(len(questions)):

                     if (
                                questions[i]["topic"] == topic
                                and student_answers[i + 1] != questions[i]["answer"]
                        ):

                                wrong_questions.append({
                                     "question": questions[i]["question"],
                                     "student_answer": student_answers[i + 1],
                                     "correct_answer": questions[i]["answer"]
                      })

            weak_topic_data.append({
                  "topic": topic,
                  "percentage": topic_scores[topic]["percentage"],
                   "wrong_questions": wrong_questions
           })
    ai_insights = {}

    if weak_topic_data:

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=(
              """You are an educational competency analysis assistant.

                Analyze the student's weak topics from a quiz.

                For every topic, return:
                - topic
                - competency_gap: identify the specific concept, skill, or ability the student struggles with based on the wrong questions. Do not simply repeat the topic name.
                - recommendation: give a practical study action that addresses the competency gap. It must be different from the competency gap.

                Return ONLY valid JSON as an array.
                Do not use markdown or ```.

                Example:
                [
                     {
                          "topic": "SQL",
                         "competency_gap": "Difficulty applying filtering and table relationships when constructing SQL queries.",
                        "recommendation": "Review SELECT, WHERE and JOIN clauses, then practice query problems combining these clauses."
                     }
      ]

      Student quiz data:

       """
                + json.dumps(weak_topic_data)
                    )
       )

        generated_insights = json.loads(response.text)

    for item in generated_insights:

        ai_insights[item["topic"]] = {
            "competency_gap": item["competency_gap"],
            "recommendation": item["recommendation"]
        }
    session["latest_performance"] = {
          "correct_count": correct_count,
          "overall_percentage": overall_percentage,
           "results": results,
          "topic_scores": topic_scores,
          "weak_topics": weak_topics,
          "ai_insights": ai_insights
    }
    return redirect("/quiz-result", code=303)

@app.route("/quiz-result")
def quiz_result():

    performance_data = session.get("latest_performance")

    if not performance_data:
        return redirect("/quiz")

    return render_template(
        "quiz_result.html",
        results=performance_data["results"],
        correct_count=performance_data["correct_count"],
        overall_percentage=performance_data["overall_percentage"]
    )

@app.route("/performance")
def performance():

    performance_data = session.get("latest_performance")

    return render_template(
        "performance.html",
        performance_data=performance_data
    )

@app.route("/weak-topics")
def weak_topics():

    performance_data = session.get("latest_performance")

    return render_template(
        "weak_topics.html",
        performance_data=performance_data
    )

@app.route("/study-plan")
def study_plan():

    performance_data = session.get("latest_performance")

    return render_template(
        "study_plan.html",
        performance_data=performance_data
    )

@app.route("/history")
def history():

    student_id = session.get("student_id")

    if not student_id:
        return redirect("/dashboard")

    connection = sqlite3.connect("learnwise.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, filename, created_at
        FROM study_materials
        WHERE student_id = ?
        ORDER BY created_at DESC
    """, (student_id,))

    materials = cursor.fetchall()

    connection.close()

    return render_template(
        "history.html",
        materials=materials,
        selected_material=None
    )

@app.route("/delete-history/<int:material_id>", methods=["POST"])
def delete_history(material_id):

    student_id = session.get("student_id")

    if not student_id:
        return redirect("/dashboard")

    connection = sqlite3.connect("learnwise.db")
    cursor = connection.cursor()

    # Get the PDF filename
    cursor.execute(
        "SELECT filename FROM study_materials WHERE id = ? AND student_id = ?",
        (material_id, student_id)
    )

    material = cursor.fetchone()

    if not material:
        connection.close()
        return "Study material not found."

    filename = material[0]

    # Delete Ask AI history
    cursor.execute(
        "DELETE FROM ai_questions WHERE material_id = ?",
        (material_id,)
    )

    # Delete summary
    cursor.execute(
        "DELETE FROM summaries WHERE material_id = ?",
        (material_id,)
    )

    # Delete generated quizzes
    cursor.execute(
        "DELETE FROM generated_quizzes WHERE material_id = ?",
        (material_id,)
    )

    # Delete study material record
    cursor.execute(
        "DELETE FROM study_materials WHERE id = ? AND student_id = ?",
        (material_id, student_id)
    )

    connection.commit()
    connection.close()

    # Delete actual PDF file
    pdf_path = os.path.join("uploads", filename)

    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    # Delete saved summary HTML file
    summary_path = os.path.join("summaries", filename + ".html")

    if os.path.exists(summary_path):
        os.remove(summary_path)

    return redirect("/history")

@app.route("/history/<int:material_id>")
def material_history(material_id):

    student_id = session.get("student_id")

    if not student_id:
        return redirect("/dashboard")

    connection = sqlite3.connect("learnwise.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, filename, created_at
        FROM study_materials
        WHERE id = ? AND student_id = ?
    """, (material_id, student_id))

    material = cursor.fetchone()

    if not material:
        connection.close()
        return "Study material not found."

    cursor.execute("""
        SELECT summary
        FROM summaries
        WHERE material_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (material_id,))

    summary_row = cursor.fetchone()

    cursor.execute("""
        SELECT question, answer, created_at
        FROM ai_questions
        WHERE material_id = ?
        ORDER BY created_at DESC
    """, (material_id,))

    questions = cursor.fetchall()

    connection.close()

    selected_material = {
        "id": material["id"],
        "filename": material["filename"],
        "created_at": material["created_at"],
        "summary": summary_row["summary"] if summary_row else None,
        "questions": [dict(q) for q in questions]
    }

    return render_template(
        "history.html",
        materials=None,
        selected_material=selected_material
    )

if __name__ == "__main__":
    app.run(debug=True) 
    


