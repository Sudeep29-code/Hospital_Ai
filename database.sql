-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: localhost    Database: hospital_db
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `doctors`
--

DROP TABLE IF EXISTS `doctors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `doctors` (
  `id` int NOT NULL AUTO_INCREMENT,
  `doctor_id` varchar(50) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `department` varchar(50) DEFAULT NULL,
  `password` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `doctor_id` (`doctor_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `doctors`
--

LOCK TABLES `doctors` WRITE;
/*!40000 ALTER TABLE `doctors` DISABLE KEYS */;
INSERT INTO `doctors` VALUES (1,'DOC001','Dr. Kaibalya','Cardiology',NULL),(3,'D1001','Dr Sharma','Cardiology','1234');
/*!40000 ALTER TABLE `doctors` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `emergency_logs`
--

DROP TABLE IF EXISTS `emergency_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `emergency_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int DEFAULT NULL,
  `doctor_id` int DEFAULT NULL,
  `timestamp` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `emergency_logs`
--

LOCK TABLES `emergency_logs` WRITE;
/*!40000 ALTER TABLE `emergency_logs` DISABLE KEYS */;
/*!40000 ALTER TABLE `emergency_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `patients`
--

DROP TABLE IF EXISTS `patients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `patients` (
  `id` int NOT NULL AUTO_INCREMENT,
  `patient_id` varchar(20) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `age` int NOT NULL,
  `oxygen_level` int DEFAULT NULL,
  `temperature` float DEFAULT NULL,
  `bp` int DEFAULT NULL,
  `disease` varchar(100) DEFAULT NULL,
  `department` varchar(50) DEFAULT NULL,
  `priority` varchar(10) DEFAULT NULL,
  `status` varchar(20) DEFAULT 'waiting',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `appointment_time` datetime DEFAULT NULL,
  `consultation_time` int DEFAULT NULL,
  `predicted_delay` int DEFAULT '0',
  `aadhaar` varchar(20) DEFAULT NULL,
  `gender` varchar(10) DEFAULT NULL,
  `dob` date DEFAULT NULL,
  `phone` varchar(15) DEFAULT NULL,
  `whatsapp` varchar(15) DEFAULT NULL,
  `blood_group` varchar(5) DEFAULT NULL,
  `address` text,
  `oxygen` float DEFAULT NULL,
  `consultation_duration` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `patient_id` (`patient_id`)
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `patients`
--

LOCK TABLES `patients` WRITE;
/*!40000 ALTER TABLE `patients` DISABLE KEYS */;
INSERT INTO `patients` VALUES (7,'P001','Tushar',0,90,900,800,'Heart','Cardiology','HIGH','completed','2026-02-13 18:44:10',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,7),(9,'P002','Tushar',0,90,900,800,'Heart','Cardiology','HIGH','completed','2026-02-13 18:44:27',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,8),(11,'P005','Tushar',5,88,39,100,'Fever','Cardiology','HIGH','completed','2026-02-13 19:01:59',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,15),(12,'P006','Tushar',30,84,37,120,'Cold','Cardiology','HIGH','completed','2026-02-13 19:02:40',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,6),(13,'P007','Tushar',25,91,38,150,'Fever','Cardiology','MEDIUM','completed','2026-02-13 19:03:15',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,22),(14,NULL,'Tushar Sahoo',18,NULL,NULL,NULL,NULL,'Orthopedics','Normal','waiting','2026-02-14 10:24:48',NULL,NULL,0,'384155909752','Female','2007-10-11','8877055278','8877055278','B+','hehhe',NULL,5),(15,NULL,'Kaibalya Tripathy',0,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 10:51:02',NULL,NULL,0,'384155909756','Male','2026-02-04','8877055278','8877055278','B+','hehhe',NULL,17),(16,NULL,'Kaibalya Tripathy',0,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 10:51:08',NULL,NULL,0,'384155909756','Male','2026-02-04','8877055278','8877055278','B+','hehhe',NULL,5),(17,NULL,'Kaibalya Tripathy',0,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 10:51:49',NULL,NULL,0,'384155909756','Female','2026-02-11','8877055278','8877055278','B+','hehhe',NULL,11),(18,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 10:57:38',NULL,NULL,0,'384155909756','Female','2026-02-26','8877055278','8877055278','B+','hehhe',NULL,15),(19,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 11:04:03',NULL,NULL,0,'384155909756','Female','2026-02-25','8877055278','8877055278','B+','hehhe',NULL,19),(20,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 11:08:49',NULL,NULL,0,'384155909756','Male','2026-02-16','8877055278','8877055278','B+','hehhe',NULL,23),(21,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 11:12:00',NULL,NULL,0,'384155909756','Female','2026-02-25','8877055278','8877055278','B+','sahoo',NULL,16),(22,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'General Medicine','NORMAL','waiting','2026-02-14 11:12:40',NULL,NULL,0,'384155909756','Female','2026-02-25','8877055278','8877055278','B+','uyy',NULL,24),(23,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Pediatrics','NORMAL','waiting','2026-02-14 12:10:11',NULL,NULL,0,'384155909756','Male','2026-02-25','8877055278','8877055278','B+','hehhe',NULL,10),(24,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Pediatrics','HIGH','waiting','2026-02-14 12:11:18',NULL,NULL,0,'384155909756','Male','2026-02-25','8877055278','8877055278','B+','hehhe',NULL,14),(25,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Orthopedics','HIGH','waiting','2026-02-14 12:12:05',NULL,NULL,0,'384155909756','Female','2026-02-25','8877055278','8877055278','B+','hehhe',NULL,15),(26,NULL,'Kaibalya Tripathy',-1,NULL,NULL,NULL,NULL,'Orthopedics','HIGH','waiting','2026-02-14 12:12:32',NULL,NULL,0,'384155909756','Male','2026-02-25','8877055278','8877055278','B+','hehhe',NULL,7),(27,NULL,'Aditya',0,NULL,NULL,NULL,NULL,'Cardiology','HIGH','completed','2026-02-14 12:28:26',NULL,NULL,0,'384155686598','Male','2026-02-14','8877055278','8877055278','B+','slls',NULL,24),(28,NULL,'Aditya',0,NULL,NULL,NULL,NULL,'Cardiology','HIGH','completed','2026-02-14 12:36:54',NULL,NULL,0,'384155686598','Female','2026-02-14','8877055278','8877055278','B+','hehhe',NULL,18),(29,NULL,'Aditya',0,NULL,NULL,NULL,NULL,'Cardiology','NORMAL','completed','2026-02-14 12:59:38',NULL,NULL,0,'384155686598','Male','2026-02-14','8877055278','8877055278','B+','hehhe',NULL,11),(30,NULL,'Kaibalya Tripathy',0,NULL,38,110,NULL,'Cardiology','NORMAL','completed','2026-02-14 13:15:32',NULL,NULL,0,'384155909756','Male','2026-02-11','8877055278','8877055278','B+','hehhe',96,18),(31,NULL,'Kaibalya Tripathy',0,NULL,38,100,NULL,'Cardiology','EMERGENCY','completed','2026-02-14 13:18:00',NULL,NULL,0,'384155909756','Female','2026-02-11','8877055278','8877055278','B+','hehhe',60,11),(32,NULL,'Kaibalya Tripathy',0,NULL,38,100,NULL,'Cardiology','EMERGENCY','completed','2026-02-14 13:28:28',NULL,NULL,0,'384155909756','Female','2026-02-11','8877055278','8877055278','B+','he',60,18),(33,NULL,'R',0,NULL,38.2,98,NULL,'Cardiology','HIGH','emergency','2026-02-14 13:44:28',NULL,NULL,0,'384155909756','Female','2026-02-11','8877055278','8877055278','B+','hehhe',63,13),(34,NULL,'R',0,NULL,38.2,98,NULL,'Cardiology','HIGH','emergency','2026-02-14 13:44:52',NULL,NULL,0,'384155909756','Female','2026-02-11','8877055278','8877055278','B+','hehhe',63,7),(35,NULL,'Kaibalya Tripathy',0,NULL,38,111,NULL,'Cardiology','MEDIUM','waiting','2026-02-14 13:47:32',NULL,NULL,0,'384155909756','Female','2026-02-10','8877055278','8877055278','B+','hehhe',99,10),(36,NULL,'Kaibalya Tripathy',0,NULL,38,111,NULL,'Cardiology','MEDIUM','waiting','2026-02-14 13:47:57',NULL,NULL,0,'384155909756','Female','2026-02-10','8877055278','8877055278','B+','hehhe',99,6);
/*!40000 ALTER TABLE `patients` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-15 18:59:39
