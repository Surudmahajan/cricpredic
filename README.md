# 🏏 CricPredic

A simple Flask-based web application that predicts the winning probabilities of cricket matches between two teams using historical performance data, and displays Live Cricket Scores

<img width="1350" height="719" alt="image" src="https://github.com/user-attachments/assets/2ded5879-8429-4c28-bc89-17e4f48c1ccc" />



## 🚀 Features
- Select **two teams** and **match format** (ODI, T20I, Test).
- Calculates win probabilities based on:
  - Average runs
  - Win ratio
  - Toss advantage
  - Opponent performance history
- Displays a **comparison chart** between teams.
- Embedded **live cricket scores** via iframes.

## Get a live demo 
[Visit CricPredic](https://cricpredic.onrender.com/)

## 🛠 Tech Stack
**Backend:** Flask, Pandas, Matplotlib, Requests, Gunicorn  
**Frontend:** HTML, Bootstrap, JavaScript  
**Data Source:** CricAPI / CSV dataset of past matches

## 📂 Project Structure
```bash
├── app.py # Flask backend
├── dataset.csv # Historical cricket data
├── templates/ # HTML templates (frontend)
├── static/ # CSS, JS, images (optional)
├── requirements.txt # Python dependencies
├── Procfile # For Render deployment
└── README.md # This file
```
## ⚡ Installation & Local Setup

1. **Clone the repository**
```bash
git clone https://github.com/Surudmahajan/cricpredic.git
cd cricpredic
```
2. **Create a virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```
3. **Install dependencies**
```bash
pip install -r requirements.txt
```
4. **Run the application**
```bash
python app.py
```
The app will run at: http://127.0.0.1:5000

## 🌐 Deployment
**This app is deployed on Render using:**

- requirements.txt

- Procfile (web: gunicorn app:app)

## ✍🏻Author

**Surud Mahajan**

## 📜 License
**This project is open-source and available under the MIT License.**



