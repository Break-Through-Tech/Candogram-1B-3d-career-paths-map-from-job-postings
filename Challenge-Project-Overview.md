# 3D Career Paths Map from Job Postings

**Company / Org:** Candogram  
**Challenge Advisor:** Henning Seip,henning.seip@candogram.com  
**AI Studio Coach:** Nagalakshmi Pulivarthi,nagalakshmi.pulivarthi@breakthroughtech.org  
**Program:** Break Through Tech AI Studio - Fall 2026

---

## 🏢 About Candogram

Candogram specializes in innovative solutions utilizing data analytics and visualization to enhance user experience in the tech industry. Our focus is on providing insights from job postings to help businesses and individuals make informed decisions about career pathways.

---

## 🎯 The Challenge

### Project Summary
In this project you will use job postings and Text Representation, Dimensionality Reduction, Sentence Embeddings, Nearest Neighbor Search to create an interactive 3D scatterplot to demonstrate career paths from entry level to senior positions. This will help prototype ideas for potential new products.

### Success Criteria
The team should have a working HTML page with a 3D scatter plot built from job postings where careers paths can be explored from entry level to senior positions, i.e. Entry Level Accountant -> Data Engineer -> Data Platform Manager -> Distinguished Engineer

### Stretch Goal
The regular version of this project uses job titles only to determine how jobs are related and the level of experience required. The stretch goal is to incorporate the job description and requirements into this model.

### Project Milestones

Use these milestones to guide your work. Your team will create a **GitHub Projects board** to track tasks within each milestone.

| Month | Milestone | Key Activities |
|-------|-----------|----------------|
| **September** | Data Preparation Complete | [TBD] |
| **October** | Data Model Complete | [TBD]  |
| **November** | Interactive 3D Scatter Plot Complete | [TBD] |

> **Note for the team:** Please create a GitHub Projects board in this repository to break these milestones into weekly tasks. Go to the **Projects** tab → **New project** → Choose **Board** → Add columns for each month.

---

## 📊 Dataset

**Name and Source:** [TBD]   
**Format:** CSV/TSV  
**Size:** under 1gb  
**Location:** https://github.com/Break-Through-Tech/Candogram-3D_Career_Paths_Map/tree/main/data

### Key Details
- Students receive a random set of job postings from the New York City job market as a ZIP file. Data format: CSV/ TSV.

---

## 🛠️ Suggested Approach

**ML Problem Type:** Classification, Clustering, Recommendation Systems, Natural Language Processing (NLP)

**Recommended Libraries:**  
   - pandas, numpy — data loading and cleaning  
   -  Hugging Face Transformers / sentence-transformers — generate embeddings from job titles and descriptions (runs locally, no API key needed)  
   -  PyTorch — deep learning backend behind sentence-transformers  
   -  umap-learn — reduce embeddings down to 3D coordinates  
   -  scikit-learn — PCA/t-SNE (alt. dimensionality reduction), NearestNeighbors, KMeans/DBSCAN clustering, and evaluation metrics
   -  faiss — optional, faster nearest neighbor search if the dataset grows
   - matplotlib, seaborn — quick 2D exploratory plots before building the 3D view  
   -  plotly — build the interactive 3D scatter plot and export to a self-contained HTML file (fig.write_html())  
   -  three.js — optional stretch-goal alternative to Plotly for a more custom web visualization   
    
 
---

## 📚 Resources to Get Started

The following resources will help your team understand the problem space and potential technical approaches for this project:

**Background Reading:**
- https://www.bls.gov/
- https://www.weforum.org/publications/the-future-of-jobs-report-2025/
- https://www.edrawmax.com/templates/collection/career-path/
- https://www.newyorkfed.org/research/college-labor-market#--:explore:unemployment

**Technical Tutorials:**
- https://www.youtube.com/watch?v=8QmkFAthuPU&t=66s
- Word2Vec: https://www.youtube.com/watch?v=viZrOnJclY0
- Dimensionality Reduction: https://www.youtube.com/watch?v=HMOI_lkzW08
In general we recommend the video libraries of Data School (https://www.youtube.com/@dataschool) and StatQuest (https://www.youtube.com/@statquest)

**Code Examples:**
- https://www.youtube.com/@dataschool

*Feel free to explore beyond these, and share anything interesting you find with me!*

---

## 🤝 How We'll Work Together

**Check-ins:** During our biweekly 45-min AI Studio Lab Section meeting block (2nd and 4th week of every month)  
**Communication:** Discord (Break Through Tech workspace)  
**Response time:** Within 48 hours on weekdays  

**Recommended Tools:**
- **Coding:** VSCode, Jupyter Notebook 
- **Collaboration:** Slack
- **Virtual Meetings:** Google Meet

---

## 🚀 Getting Started

1. **Review this overview document** and note any questions for our first meeting
2. **Begin reviewing the dataset** using the link above
3. **Read the GitHub Projects documentation** [here](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)

I'm excited to work with you!

---

## ❓ Questions?

Please bring any questions to our first meeting during the week of August 24th (Break Through Tech's Bridge to Studio - Session C).

---
