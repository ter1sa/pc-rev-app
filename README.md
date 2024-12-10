# Program Committee Formation Web App

This is the backend for Program Committee Formation Web App, check out the pc-rev-web for more information.

---

## Installation Steps
1. run uvicorn main:app --reload --port 8000
2. run npm start

Note: run both at the same time

## Setting up MySQL database
1. Create schema e.g. fyp-pc
2. Create the respective tables, SancusDB and Candidate_Rec
3. For SancusDB, either import your own Sancus database, or create it manually in MySQL (but it must be filled with the respective information):
   CREATE TABLE sancusdb (
    id INT(11) NOT NULL PRIMARY KEY,
    name VARCHAR(32) CHARACTER SET utf8mb4 NOT NULL,
    country VARCHAR(14) CHARACTER SET utf8mb4 NOT NULL,
    countryoforigin VARCHAR(15) CHARACTER SET utf8mb4 NOT NULL,
    email VARCHAR(41) CHARACTER SET utf8mb4 NOT NULL,
    organization VARCHAR(114) CHARACTER SET utf8mb4 NOT NULL,
    dblp VARCHAR(83) CHARACTER SET utf8mb4 NOT NULL
);
4.  For Candidate_Rec, create an empty table:
   CREATE TABLE candidate_rec (
    ID INT(11) NOT NULL PRIMARY KEY,
    NAME VARCHAR(27) CHARACTER SET utf8mb4 NOT NULL,
    EMAIL VARCHAR(47) CHARACTER SET utf8mb4 NOT NULL,
    INSTITUTE VARCHAR(60) CHARACTER SET utf8mb4 NOT NULL,
    COUNTRY VARCHAR(14) CHARACTER SET utf8mb4 NOT NULL,
    COUNTRYOFORIGIN VARCHAR(14) CHARACTER SET utf8mb4 NOT NULL,
    GENDER VARCHAR(6) CHARACTER SET utf8mb4 NOT NULL,
    LEVEL VARCHAR(6) CHARACTER SET utf8mb4 NOT NULL,
    EXPERTISE VARCHAR(93) CHARACTER SET utf8mb4 NOT NULL,
    DBLP VARCHAR(83) CHARACTER SET utf8mb4 NOT NULL,
    ITERATION INT(11) NOT NULL,
    DECISION VARCHAR(9) CHARACTER SET utf8mb4 NOT NULL,
    coauthor_hist JSON,
    years_of_pub JSON,
    coauthors JSON,
    isSelected TINYINT(1) NOT NULL
);
