DROP DATABASE IF EXISTS hospital_db;
CREATE DATABASE hospital_db;
USE hospital_db;

-- =========================
-- TABLE: admin_logs
-- =========================
CREATE TABLE admin_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- TABLE: admin_users
-- =========================
CREATE TABLE admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- TABLE: admins
-- =========================
CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

INSERT INTO admins VALUES
(3,'admin','scrypt:32768:8:1$KpDXVN41NCTADMry$28fabf2806e2b873f0a7f715e5e9d967f864503b9e30a939d17c74c37d6b9524eda8399c8128e0c5936024499e14e2211919839a6b94320b985795eb3e204781');

-- =========================
-- TABLE: ai_settings
-- =========================
CREATE TABLE ai_settings (
    id INT PRIMARY KEY DEFAULT 1,
    fairness_weight FLOAT DEFAULT 0.6,
    wait_weight FLOAT DEFAULT 0.4,
    overload_threshold INT DEFAULT 10,
    cooldown_minutes INT DEFAULT 5,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO ai_settings VALUES
(1,0.6,0.4,10,5,'2026-02-18 00:51:59');

-- =========================
-- TABLE: system_settings
-- =========================
CREATE TABLE system_settings (
    id INT PRIMARY KEY DEFAULT 1,
    fairness_weight FLOAT DEFAULT 0.6,
    wait_weight FLOAT DEFAULT 0.4,
    overload_threshold FLOAT DEFAULT 85,
    cooldown_minutes INT DEFAULT 5,
    target_avg_load INT DEFAULT 5,
    optimizer_interval INT DEFAULT 20
);

INSERT INTO system_settings VALUES
(1,0.6,0.4,85,5,5,20);

-- =========================
-- TABLE: doctors
-- =========================
CREATE TABLE doctors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_code VARCHAR(10) UNIQUE,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    password VARCHAR(100),
    total_consultation_time INT DEFAULT 0,
    patients_completed INT DEFAULT 0,
    available_from TIME NOT NULL DEFAULT '09:00:00',
    available_to TIME NOT NULL DEFAULT '17:00:00',
    is_active INT DEFAULT 1,
    on_shift TINYINT(1) DEFAULT 1,
    status VARCHAR(20) DEFAULT 'Available'
);

INSERT INTO doctors VALUES
(4,'DOC004','Tushar Sahoo','General Medicine','12345',82,4,'06:00:00','17:00:00',1,1,'Available'),
(5,'DOC005','Kaibalya Tripathy','Cardiology','12345',34,3,'05:00:00','17:00:00',1,1,'Available'),
(6,'DOC006','Devi Prasad Behera','Cardiology','12345',58,3,'06:00:00','22:00:00',1,1,'Available');

-- =========================
-- TABLE: patients
-- =========================
CREATE TABLE patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(20) UNIQUE,
    name VARCHAR(100),
    age INT NOT NULL,
    oxygen_level INT,
    temperature FLOAT,
    bp INT,
    disease VARCHAR(100),
    department VARCHAR(50),
    priority VARCHAR(10),
    status VARCHAR(20) DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    appointment_time DATETIME,
    consultation_time INT,
    predicted_delay INT DEFAULT 0,
    aadhaar VARCHAR(20),
    gender VARCHAR(10),
    dob DATE,
    phone VARCHAR(15),
    whatsapp VARCHAR(15),
    blood_group VARCHAR(5),
    address TEXT,
    oxygen FLOAT,
    consultation_duration FLOAT,
    no_show_probability FLOAT DEFAULT 0,
    last_reassigned_at DATETIME,
    doctor_id INT,
    priority_score FLOAT DEFAULT 0,
    completed_at DATETIME,
    duration_explanation TEXT,
    no_show_explanation TEXT
);

-- (Only 2 sample inserts shown below due to size; repeat for all rows if needed)

INSERT INTO patients 
(id,name,age,temperature,bp,disease,department,priority,status,created_at,aadhaar,gender,dob,phone,whatsapp,blood_group,address,oxygen,consultation_duration,no_show_probability,doctor_id)
VALUES
(1,'Jam',18,38.8,120,'cold','General Medicine','MEDIUM','waiting','2026-02-18 22:23:30','384155909751','Male','2007-10-11','8877055278','8877055278','B+','wwew',99,18.03,0.34,NULL),
(12,'Anand',30,38,120,'Asthma','General Medicine','LOW','waiting','2026-02-19 15:31:57','384155909756','Male','1995-10-11','8877055278','8877055278','AB+','wwew',98,12.24,0.34,4);

-- =========================
-- TABLE: reassignment_logs
-- =========================
CREATE TABLE reassignment_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    department VARCHAR(100),
    patient_id INT,
    from_doctor INT,
    to_doctor INT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- TABLE: emergency_logs
-- =========================
CREATE TABLE emergency_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    doctor_id INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- TABLE: assignment_explanations
-- =========================
CREATE TABLE assignment_explanations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    doctor_id INT,
    department VARCHAR(100),
    predicted_duration FLOAT,
    doctor_load INT,
    no_show_probability FLOAT,
    rl_action VARCHAR(50),
    final_cost FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);





--inserting data into patients.
INSERT INTO patients
(name, age, temperature, bp, disease, department, priority, status, created_at,
 aadhaar, gender, dob, phone, whatsapp, blood_group, address,
 oxygen, consultation_duration, no_show_probability, doctor_id)

SELECT
    CONCAT('Patient_', n) AS name,
    FLOOR(1 + RAND()*90) AS age,
    ROUND(97 + RAND()*6,1) AS temperature,
    FLOOR(90 + RAND()*60) AS bp,
    ELT(FLOOR(1 + RAND()*5),'Cold','Fever','Asthma','Diabetes','Infection') AS disease,
    'General Medicine' AS department,
    ELT(FLOOR(1 + RAND()*3),'LOW','MEDIUM','HIGH') AS priority,
    'waiting' AS status,
    NOW() AS created_at,
    LPAD(FLOOR(RAND()*1000000000000),12,'3') AS aadhaar,
    ELT(FLOOR(1 + RAND()*2),'Male','Female') AS gender,
    DATE_SUB(CURDATE(), INTERVAL FLOOR(1 + RAND()*30000) DAY) AS dob,
    LPAD(FLOOR(RAND()*10000000000),10,'8') AS phone,
    LPAD(FLOOR(RAND()*10000000000),10,'9') AS whatsapp,
    ELT(FLOOR(1 + RAND()*8),'A+','A-','B+','B-','O+','O-','AB+','AB-') AS blood_group,
    'Sample Address' AS address,
    FLOOR(85 + RAND()*15) AS oxygen,
    ROUND(5 + RAND()*25,2) AS consultation_duration,
    ROUND(RAND(),2) AS no_show_probability,
    FLOOR(1 + RAND()*5) AS doctor_id
FROM (
    SELECT @row := @row + 1 AS n
    FROM information_schema.tables,
         (SELECT @row := 0) r
    LIMIT 1000
) numbers;