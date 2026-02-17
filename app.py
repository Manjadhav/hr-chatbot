print("HR CHATBOT SERVER STARTED")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
import sqlite3
import os
import uuid

app = FastAPI()

# ----------------------------
# SETUP
# ----------------------------
os.makedirs("uploads", exist_ok=True)

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    experience TEXT,
    cv_path TEXT
)
""")
conn.commit()

ADMIN_PASSWORD = "admin123"

# ----------------------------
# HOME PAGE (CHATBOT)
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="font-family:Arial;background:#ece5dd">
    <h2>HR Recruitment Chatbot</h2>

    <div id="chatbox" style="
        background:white;
        height:350px;
        width:420px;
        overflow:auto;
        padding:10px;
        border-radius:10px;
        border:1px solid #ccc;">
    </div>

    <br>
    <input id="message" type="text" placeholder="Type message" style="width:300px">
    <button onclick="sendMessage()">Send</button>

    <br><br>
    <h3>Upload CV</h3>
    <input type="file" id="cvfile">
    <button onclick="uploadCV()">Upload CV</button>

    <script>
    let stage = 0;
    let candidate_id = localStorage.getItem("candidate_id");

    function addMsg(sender, text){
        let box = document.getElementById("chatbox");
        box.innerHTML += "<p><b>"+sender+":</b> "+text+"</p>";
        box.scrollTop = box.scrollHeight;
    }

    async function sendMessage() {
        let input = document.getElementById("message");
        let message = input.value;
        addMsg("You", message);

        const response = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                message: message,
                stage: stage,
                candidate_id: candidate_id
            })
        });

        const data = await response.json();
        stage = data.stage;
        candidate_id = data.candidate_id;
        localStorage.setItem("candidate_id", candidate_id);

        addMsg("Bot", data.reply);
        input.value = "";
    }

    async function uploadCV() {
        if (!candidate_id) {
            alert("Complete chat first.");
            return;
        }

        let fileInput = document.getElementById("cvfile");
        if (fileInput.files.length === 0) {
            alert("Select CV first");
            return;
        }

        let formData = new FormData();
        formData.append("file", fileInput.files[0]);
        formData.append("candidate_id", candidate_id);

        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();
        alert(data.message);
    }
    </script>
    </body>
    </html>
    """

# ----------------------------
# CHAT LOGIC
# ----------------------------
from pydantic import BaseModel

class ChatData(BaseModel):
    message: str
    stage: int
    candidate_id: int | None = None

@app.post("/chat")
async def chat(data: ChatData):
    stage = data.stage
    candidate_id = data.candidate_id

    if stage == 0:
        cursor.execute("INSERT INTO candidates (name,email,experience) VALUES ('','','')")
        conn.commit()
        candidate_id = cursor.lastrowid
        return {"reply": "Welcome! What is your name?",
                "stage": 1,
                "candidate_id": candidate_id}

    elif stage == 1:
        cursor.execute("UPDATE candidates SET name=? WHERE id=?",
                       (data.message, candidate_id))
        conn.commit()
        return {"reply": "Enter your email.",
                "stage": 2,
                "candidate_id": candidate_id}

    elif stage == 2:
        cursor.execute("UPDATE candidates SET email=? WHERE id=?",
                       (data.message, candidate_id))
        conn.commit()
        return {"reply": "Years of experience?",
                "stage": 3,
                "candidate_id": candidate_id}

    elif stage == 3:
        cursor.execute("UPDATE candidates SET experience=? WHERE id=?",
                       (data.message, candidate_id))
        conn.commit()
        return {"reply": "Please upload your CV below.",
                "stage": 4,
                "candidate_id": candidate_id}

    return {"reply": "Waiting for CV upload.",
            "stage": stage,
            "candidate_id": candidate_id}

# ----------------------------
# UPLOAD CV
# ----------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...),
                 candidate_id: int = Form(...)):

    filename = str(uuid.uuid4()) + "_" + file.filename
    path = f"uploads/{filename}"

    with open(path, "wb") as f:
        f.write(await file.read())

    cursor.execute("UPDATE candidates SET cv_path=? WHERE id=?",
                   (path, candidate_id))
    conn.commit()

    return {"message": "CV uploaded successfully!"}

# ----------------------------
# ADMIN LOGIN PAGE
# ----------------------------
@app.get("/admin", response_class=HTMLResponse)
def admin_login():
    return """
    <h2>Admin Login</h2>
    <form method="post">
        <input type="password" name="password" placeholder="Enter password">
        <button type="submit">Login</button>
    </form>
    """

@app.post("/admin")
def admin_auth(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        return RedirectResponse("/dashboard", status_code=302)
    raise HTTPException(status_code=403, detail="Wrong password")

# ----------------------------
# ADMIN DASHBOARD (TABLE UI)
# ----------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    cursor.execute("SELECT * FROM candidates")
    rows = cursor.fetchall()

    html = "<h2>Candidate Dashboard</h2><table border='1' cellpadding='10'>"
    html += "<tr><th>ID</th><th>Name</th><th>Email</th><th>Experience</th><th>CV</th><th>Action</th></tr>"

    for r in rows:
        cv_link = f"<a href='/download/{r[0]}'>Download CV</a>" if r[4] else "Not Uploaded"
        delete_link = f"<a href='/delete/{r[0]}'>Delete</a>"

        html += f"""
        <tr>
        <td>{r[0]}</td>
        <td>{r[1]}</td>
        <td>{r[2]}</td>
        <td>{r[3]}</td>
        <td>{cv_link}</td>
        <td>{delete_link}</td>
        </tr>
        """

    html += "</table>"
    return html

# ----------------------------
# DOWNLOAD CV (SAFE)
# ----------------------------
@app.get("/download/{candidate_id}")
def download(candidate_id: int):
    cursor.execute("SELECT cv_path FROM candidates WHERE id=?",
                   (candidate_id,))
    row = cursor.fetchone()
    if row and row[0]:
        return FileResponse(row[0])
    raise HTTPException(status_code=404, detail="CV not found")

# ----------------------------
# DELETE CANDIDATE
# ----------------------------
@app.get("/delete/{candidate_id}")
def delete(candidate_id: int):
    cursor.execute("DELETE FROM candidates WHERE id=?",
                   (candidate_id,))
    conn.commit()
    return RedirectResponse("/dashboard", status_code=302)


