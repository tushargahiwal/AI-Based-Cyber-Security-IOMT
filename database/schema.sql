-- ============================================================================
-- AI-Based Cyber Attack Detection in the IoMT — Complete Database Schema
-- Engine: MySQL 8.0, InnoDB, utf8mb4_unicode_ci
-- Source: docs/IoMT_Attack_Detection_Build_Document.pdf, Section 10
-- Run: mysql -u root -p < database/schema.sql
--
-- Safe to re-run. Tables use IF NOT EXISTS and the data section at the bottom
-- uses ON DUPLICATE KEY UPDATE, so loading this twice changes nothing.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS iomt_ids
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE iomt_ids;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- A. IDENTITY & ACCESS
-- ============================================================================

CREATE TABLE IF NOT EXISTS roles (
  id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(50)  NOT NULL,
  description VARCHAR(255) DEFAULT NULL,
  permissions JSON NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_roles_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  role_id             TINYINT UNSIGNED NOT NULL,
  username            VARCHAR(64)  NOT NULL,
  email               VARCHAR(150) NOT NULL,
  password_hash       VARCHAR(255) NOT NULL,
  full_name           VARCHAR(150) DEFAULT NULL,
  department          VARCHAR(100) DEFAULT NULL,
  mobile              VARCHAR(15) DEFAULT NULL,
  address             VARCHAR(255) DEFAULT NULL,
  city                VARCHAR(100) DEFAULT NULL,
  state               VARCHAR(100) DEFAULT NULL,
  is_active           BOOLEAN NOT NULL DEFAULT TRUE,
  mfa_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
  last_login_at       DATETIME DEFAULT NULL,
  failed_login_count  SMALLINT NOT NULL DEFAULT 0,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at          DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email),
  CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS user_sessions (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id             BIGINT UNSIGNED NOT NULL,
  refresh_token_hash  VARCHAR(255) NOT NULL,
  ip_address          VARCHAR(45) DEFAULT NULL,
  user_agent          VARCHAR(255) DEFAULT NULL,
  issued_at           DATETIME NOT NULL,
  expires_at          DATETIME NOT NULL,
  revoked             BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id),
  KEY idx_sessions_user (user_id),
  CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_logs (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED DEFAULT NULL,
  action      VARCHAR(100) NOT NULL,
  entity_type VARCHAR(50)  DEFAULT NULL,
  entity_id   BIGINT UNSIGNED DEFAULT NULL,
  old_value   JSON DEFAULT NULL,
  new_value   JSON DEFAULT NULL,
  ip_address  VARCHAR(45) DEFAULT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_created (created_at),
  KEY idx_audit_user (user_id),
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- ============================================================================
-- B. CLINICAL & ASSET INVENTORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS wards (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name            VARCHAR(100) NOT NULL,
  floor           VARCHAR(20) DEFAULT NULL,
  network_segment VARCHAR(50) DEFAULT NULL,
  criticality     ENUM('low','medium','high','critical') NOT NULL DEFAULT 'medium',
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS device_types (
  id                      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  type_name               VARCHAR(100) NOT NULL,
  category                ENUM('sensor','actuator','gateway','hybrid') NOT NULL,
  is_life_critical        BOOLEAN NOT NULL DEFAULT FALSE,
  default_protocols       JSON DEFAULT NULL,
  expected_data_rate_kbps DECIMAL(8,2) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_device_type_name (type_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS devices (
  id                        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_uid                VARCHAR(64) NOT NULL,
  device_type_id            INT UNSIGNED NOT NULL,
  ward_id                   INT UNSIGNED DEFAULT NULL,
  manufacturer              VARCHAR(100) DEFAULT NULL,
  model_number              VARCHAR(100) DEFAULT NULL,
  firmware_version          VARCHAR(50) DEFAULT NULL,
  ip_address                VARCHAR(45) DEFAULT NULL,
  mac_address                VARCHAR(17) DEFAULT NULL,
  registered_mac_ip_binding VARCHAR(64) DEFAULT NULL,
  mqtt_client_id            VARCHAR(100) DEFAULT NULL,
  status                    ENUM('online','offline','quarantined','maintenance') NOT NULL DEFAULT 'offline',
  trust_score                DECIMAL(5,2) NOT NULL DEFAULT 100.00,
  last_seen_at               DATETIME DEFAULT NULL,
  -- Quarantine is time-limited by default: a life-critical device that is
  -- cut off and then forgotten is a patient-safety incident of its own.
  quarantined_until          DATETIME DEFAULT NULL,
  created_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_device_uid (device_uid),
  UNIQUE KEY uq_device_mac (mac_address),
  KEY idx_device_ip (ip_address),
  KEY idx_device_last_seen (last_seen_at),
  CONSTRAINT fk_devices_type FOREIGN KEY (device_type_id) REFERENCES device_types(id),
  CONSTRAINT fk_devices_ward FOREIGN KEY (ward_id) REFERENCES wards(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS device_profiles (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id           BIGINT UNSIGNED NOT NULL,
  baseline_vector     JSON NOT NULL,
  baseline_std        JSON NOT NULL,
  typical_ports       JSON DEFAULT NULL,
  typical_peers       JSON DEFAULT NULL,
  modal_ttl           SMALLINT DEFAULT NULL,
  avg_pkts_per_sec    DECIMAL(10,3) DEFAULT NULL,
  active_hours        JSON DEFAULT NULL,
  samples_used        INT UNSIGNED DEFAULT NULL,
  profile_version     INT NOT NULL DEFAULT 1,
  last_recomputed_at  DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_profile_device (device_id),
  CONSTRAINT fk_profile_device FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS patients (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  patient_code       VARCHAR(32) NOT NULL,
  age_band           VARCHAR(16) DEFAULT NULL,
  sex                ENUM('M','F','O','U') DEFAULT NULL,
  ward_id            INT UNSIGNED DEFAULT NULL,
  admitted_at        DATETIME DEFAULT NULL,
  discharged_at      DATETIME DEFAULT NULL,
  baseline_hr_min    SMALLINT DEFAULT NULL,
  baseline_hr_max    SMALLINT DEFAULT NULL,
  baseline_spo2_min  TINYINT DEFAULT NULL,
  notes              VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_patient_code (patient_code),
  CONSTRAINT fk_patients_ward FOREIGN KEY (ward_id) REFERENCES wards(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS patient_device_assignments (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  patient_id   BIGINT UNSIGNED NOT NULL,
  device_id    BIGINT UNSIGNED NOT NULL,
  assigned_at  DATETIME NOT NULL,
  released_at  DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_device_assigned (device_id, assigned_at),
  KEY idx_pda_patient (patient_id),
  CONSTRAINT fk_pda_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
  CONSTRAINT fk_pda_device FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB;

-- ============================================================================
-- D. REFERENCE DATA (created before Telemetry/ML/Detection tables that use it)
-- ============================================================================

CREATE TABLE IF NOT EXISTS datasets (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name           VARCHAR(100) NOT NULL,
  version        VARCHAR(20) DEFAULT NULL,
  source_url     VARCHAR(255) DEFAULT NULL,
  total_records  BIGINT UNSIGNED DEFAULT NULL,
  num_features   SMALLINT DEFAULT NULL,
  num_classes    SMALLINT DEFAULT NULL,
  benign_ratio   DECIMAL(5,4) DEFAULT NULL,
  citation       TEXT,
  notes          TEXT,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dataset_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attack_types (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  code                VARCHAR(40) NOT NULL,
  family              ENUM('BENIGN','DDOS','DOS','RECON','MQTT','SPOOFING','MALWARE','UNKNOWN') NOT NULL,
  display_name        VARCHAR(100) DEFAULT NULL,
  description         TEXT,
  default_severity    ENUM('info','low','medium','high','critical') DEFAULT NULL,
  mitre_technique      VARCHAR(20) DEFAULT NULL,
  typical_indicators   JSON DEFAULT NULL,
  recommended_action   TEXT,
  PRIMARY KEY (id),
  UNIQUE KEY uq_attack_code (code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS protocols (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name          VARCHAR(50) NOT NULL,
  default_port  INT UNSIGNED DEFAULT NULL,
  is_medical    BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id),
  UNIQUE KEY uq_protocol_name (name)
) ENGINE=InnoDB;

-- ============================================================================
-- C. TELEMETRY (high volume — partition by month in production, see §10.5)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vital_readings (
  id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id            BIGINT UNSIGNED NOT NULL,
  patient_id           BIGINT UNSIGNED DEFAULT NULL,
  recorded_at          DATETIME(3) NOT NULL,
  heart_rate           SMALLINT DEFAULT NULL,
  spo2                 TINYINT DEFAULT NULL,
  systolic_bp          SMALLINT DEFAULT NULL,
  diastolic_bp         SMALLINT DEFAULT NULL,
  body_temp            DECIMAL(4,2) DEFAULT NULL,
  respiration_rate     TINYINT DEFAULT NULL,
  raw_payload          JSON DEFAULT NULL,
  is_plausible         BOOLEAN NOT NULL DEFAULT TRUE,
  predicted_values     JSON DEFAULT NULL,
  residual_zscore      DECIMAL(6,3) DEFAULT NULL,
  injection_suspected  BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id),
  KEY idx_vitals_device (device_id),
  KEY idx_vitals_recorded (recorded_at),
  KEY idx_vitals_device_time (device_id, recorded_at),
  KEY idx_vitals_injection (injection_suspected),
  CONSTRAINT fk_vitals_device FOREIGN KEY (device_id) REFERENCES devices(id),
  CONSTRAINT fk_vitals_patient FOREIGN KEY (patient_id) REFERENCES patients(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS network_flows (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  flow_uid            CHAR(36) NOT NULL,
  device_id           BIGINT UNSIGNED DEFAULT NULL,
  src_ip              VARCHAR(45) NOT NULL,
  dst_ip              VARCHAR(45) NOT NULL,
  src_port            INT UNSIGNED DEFAULT NULL,
  dst_port            INT UNSIGNED DEFAULT NULL,
  protocol            ENUM('TCP','UDP','ICMP','MQTT','HTTP','BLE','OTHER') NOT NULL,
  src_mac             VARCHAR(17) DEFAULT NULL,
  dst_mac             VARCHAR(17) DEFAULT NULL,
  flow_start          DATETIME(3) NOT NULL,
  flow_end            DATETIME(3) NOT NULL,
  duration_ms         INT UNSIGNED DEFAULT NULL,
  total_fwd_packets   INT UNSIGNED DEFAULT 0,
  total_bwd_packets   INT UNSIGNED DEFAULT 0,
  total_fwd_bytes     BIGINT UNSIGNED DEFAULT 0,
  total_bwd_bytes     BIGINT UNSIGNED DEFAULT 0,
  capture_source      ENUM('live','pcap','dataset','simulated') NOT NULL DEFAULT 'live',
  pcap_reference      VARCHAR(255) DEFAULT NULL,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_flow_uid (flow_uid),
  KEY idx_flow_device_time (device_id, flow_start),
  KEY idx_flow_src (src_ip),
  KEY idx_flow_dst (dst_ip),
  CONSTRAINT fk_flows_device FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS flow_features (
  id                        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  flow_id                   BIGINT UNSIGNED NOT NULL,
  feature_vector            JSON NOT NULL,
  feature_set_version       VARCHAR(20) NOT NULL,
  flow_bytes_per_sec        DECIMAL(14,3) DEFAULT NULL,
  flow_packets_per_sec      DECIMAL(14,3) DEFAULT NULL,
  syn_ratio                 DECIMAL(5,4) DEFAULT NULL,
  rst_ratio                 DECIMAL(5,4) DEFAULT NULL,
  down_up_ratio             DECIMAL(10,4) DEFAULT NULL,
  pkt_len_mean              DECIMAL(10,3) DEFAULT NULL,
  pkt_len_std               DECIMAL(10,3) DEFAULT NULL,
  iat_mean_ms               DECIMAL(12,3) DEFAULT NULL,
  ttl_deviation              SMALLINT DEFAULT NULL,
  payload_entropy            DECIMAL(6,4) DEFAULT NULL,
  mqtt_connect_ratio         DECIMAL(5,4) DEFAULT NULL,
  device_profile_deviation   DECIMAL(10,4) DEFAULT NULL,
  arp_binding_violation      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_features_flow (flow_id),
  CONSTRAINT fk_features_flow FOREIGN KEY (flow_id) REFERENCES network_flows(id)
) ENGINE=InnoDB;

-- ============================================================================
-- E. ML LIFECYCLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS ml_models (
  id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  model_code            VARCHAR(40) NOT NULL,
  display_name          VARCHAR(100) DEFAULT NULL,
  stage                 TINYINT DEFAULT NULL,
  algorithm             VARCHAR(60) DEFAULT NULL,
  task_type             ENUM('binary','multiclass','anomaly','regression','meta') DEFAULT NULL,
  version               VARCHAR(20) NOT NULL,
  artifact_path         VARCHAR(255) NOT NULL,
  scaler_path           VARCHAR(255) DEFAULT NULL,
  feature_set_version   VARCHAR(20) DEFAULT NULL,
  hyperparameters       JSON DEFAULT NULL,
  input_dim             SMALLINT DEFAULT NULL,
  output_classes        JSON DEFAULT NULL,
  threshold             DECIMAL(6,4) DEFAULT NULL,
  is_active              BOOLEAN NOT NULL DEFAULT FALSE,
  trained_at             DATETIME DEFAULT NULL,
  trained_by             BIGINT UNSIGNED DEFAULT NULL,
  created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_model_code (model_code),
  CONSTRAINT fk_models_trained_by FOREIGN KEY (trained_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS training_runs (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  model_id           INT UNSIGNED NOT NULL,
  dataset_id         INT UNSIGNED DEFAULT NULL,
  run_uid            CHAR(36) NOT NULL,
  train_size         INT UNSIGNED DEFAULT NULL,
  val_size           INT UNSIGNED DEFAULT NULL,
  test_size          INT UNSIGNED DEFAULT NULL,
  resampling_method  VARCHAR(50) DEFAULT NULL,
  epochs             INT DEFAULT NULL,
  batch_size         INT DEFAULT NULL,
  duration_seconds   INT UNSIGNED DEFAULT NULL,
  hardware           VARCHAR(100) DEFAULT NULL,
  status             ENUM('running','completed','failed') NOT NULL DEFAULT 'running',
  loss_curve         JSON DEFAULT NULL,
  notes              TEXT,
  started_at         DATETIME DEFAULT NULL,
  finished_at        DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_run_uid (run_uid),
  KEY idx_runs_model (model_id),
  CONSTRAINT fk_runs_model FOREIGN KEY (model_id) REFERENCES ml_models(id),
  CONSTRAINT fk_runs_dataset FOREIGN KEY (dataset_id) REFERENCES datasets(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS model_metrics (
  id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  training_run_id        BIGINT UNSIGNED NOT NULL,
  split                  ENUM('train','validation','test','cross_dataset') NOT NULL,
  class_label            VARCHAR(50) DEFAULT NULL,
  accuracy               DECIMAL(7,6) DEFAULT NULL,
  `precision`            DECIMAL(7,6) DEFAULT NULL,
  `recall`               DECIMAL(7,6) DEFAULT NULL,
  f1_score               DECIMAL(7,6) DEFAULT NULL,
  roc_auc                DECIMAL(7,6) DEFAULT NULL,
  pr_auc                 DECIMAL(7,6) DEFAULT NULL,
  false_positive_rate     DECIMAL(7,6) DEFAULT NULL,
  false_negative_rate     DECIMAL(7,6) DEFAULT NULL,
  support                 INT UNSIGNED DEFAULT NULL,
  confusion_matrix        JSON DEFAULT NULL,
  avg_inference_ms         DECIMAL(8,3) DEFAULT NULL,
  created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_metrics_run (training_run_id),
  CONSTRAINT fk_metrics_run FOREIGN KEY (training_run_id) REFERENCES training_runs(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feature_importances (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  model_id         INT UNSIGNED NOT NULL,
  feature_name     VARCHAR(80) NOT NULL,
  importance_gain  DECIMAL(10,8) DEFAULT NULL,
  shap_mean_abs    DECIMAL(10,8) DEFAULT NULL,
  `rank`           SMALLINT DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_importances_model (model_id),
  CONSTRAINT fk_importances_model FOREIGN KEY (model_id) REFERENCES ml_models(id)
) ENGINE=InnoDB;

-- ============================================================================
-- F. DETECTION & RESPONSE
-- ============================================================================

CREATE TABLE IF NOT EXISTS detections (
  id                             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  flow_id                        BIGINT UNSIGNED NOT NULL,
  device_id                      BIGINT UNSIGNED DEFAULT NULL,
  stage1_model_id                INT UNSIGNED DEFAULT NULL,
  stage1_label                   ENUM('benign','malicious') NOT NULL,
  stage1_probability             DECIMAL(6,5) DEFAULT NULL,
  stage2_model_id                INT UNSIGNED DEFAULT NULL,
  stage2_attack_type_id          INT UNSIGNED DEFAULT NULL,
  stage2_confidence              DECIMAL(6,5) DEFAULT NULL,
  stage2_class_probs             JSON DEFAULT NULL,
  stage3_model_id                INT UNSIGNED DEFAULT NULL,
  stage3_reconstruction_error    DECIMAL(12,8) DEFAULT NULL,
  stage3_anomaly_score           DECIMAL(10,6) DEFAULT NULL,
  stage3_is_anomaly              BOOLEAN NOT NULL DEFAULT FALSE,
  stage4_injection_suspected     BOOLEAN NOT NULL DEFAULT FALSE,
  stage4_max_zscore              DECIMAL(8,4) DEFAULT NULL,
  final_verdict                  ENUM('benign','known_attack','zero_day_suspect','data_integrity','uncertain') NOT NULL,
  final_confidence                DECIMAL(6,5) DEFAULT NULL,
  severity                        ENUM('info','low','medium','high','critical') NOT NULL DEFAULT 'info',
  inference_latency_ms            DECIMAL(8,3) DEFAULT NULL,
  detected_at                     DATETIME(3) NOT NULL,
  PRIMARY KEY (id),
  KEY idx_det_flow (flow_id),
  KEY idx_det_device_time (device_id, detected_at),
  KEY idx_det_verdict (final_verdict, severity),
  CONSTRAINT fk_det_flow FOREIGN KEY (flow_id) REFERENCES network_flows(id),
  CONSTRAINT fk_det_device FOREIGN KEY (device_id) REFERENCES devices(id),
  CONSTRAINT fk_det_stage1_model FOREIGN KEY (stage1_model_id) REFERENCES ml_models(id),
  CONSTRAINT fk_det_stage2_model FOREIGN KEY (stage2_model_id) REFERENCES ml_models(id),
  CONSTRAINT fk_det_stage3_model FOREIGN KEY (stage3_model_id) REFERENCES ml_models(id),
  CONSTRAINT fk_det_attack FOREIGN KEY (stage2_attack_type_id) REFERENCES attack_types(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS explanations (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  detection_id  BIGINT UNSIGNED NOT NULL,
  method        ENUM('SHAP','LIME') NOT NULL DEFAULT 'SHAP',
  base_value    DECIMAL(12,8) DEFAULT NULL,
  top_features  JSON NOT NULL,
  narrative     TEXT,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_explanation_detection (detection_id),
  CONSTRAINT fk_explanation_detection FOREIGN KEY (detection_id) REFERENCES detections(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alerts (
  id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  alert_uid             VARCHAR(20) NOT NULL,
  detection_id          BIGINT UNSIGNED NOT NULL,
  device_id             BIGINT UNSIGNED DEFAULT NULL,
  patient_id            BIGINT UNSIGNED DEFAULT NULL,
  attack_type_id        INT UNSIGNED DEFAULT NULL,
  title                 VARCHAR(200) NOT NULL,
  description           TEXT,
  severity              ENUM('info','low','medium','high','critical') NOT NULL,
  risk_score            DECIMAL(5,2) DEFAULT NULL,
  status                ENUM('new','acknowledged','investigating','resolved','false_positive') NOT NULL DEFAULT 'new',
  assigned_to           BIGINT UNSIGNED DEFAULT NULL,
  correlated_alert_id   BIGINT UNSIGNED DEFAULT NULL,
  occurrence_count       INT UNSIGNED NOT NULL DEFAULT 1,
  first_seen_at           DATETIME(3) NOT NULL,
  last_seen_at            DATETIME(3) NOT NULL,
  acknowledged_at         DATETIME DEFAULT NULL,
  resolved_at             DATETIME DEFAULT NULL,
  resolution_notes         TEXT,
  created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_alert_uid (alert_uid),
  KEY idx_alert_status_sev (status, severity),
  KEY idx_alert_device (device_id),
  CONSTRAINT fk_alert_detection FOREIGN KEY (detection_id) REFERENCES detections(id),
  CONSTRAINT fk_alert_device FOREIGN KEY (device_id) REFERENCES devices(id),
  CONSTRAINT fk_alert_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
  CONSTRAINT fk_alert_attack_type FOREIGN KEY (attack_type_id) REFERENCES attack_types(id),
  CONSTRAINT fk_alert_user FOREIGN KEY (assigned_to) REFERENCES users(id),
  CONSTRAINT fk_alert_correlated FOREIGN KEY (correlated_alert_id) REFERENCES alerts(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alert_actions (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  alert_id          BIGINT UNSIGNED NOT NULL,
  user_id           BIGINT UNSIGNED DEFAULT NULL,
  action            ENUM('created','acknowledged','assigned','commented','escalated','mitigated','reverted','resolved','marked_false_positive','reopened') NOT NULL,
  comment           TEXT,
  previous_status   VARCHAR(30) DEFAULT NULL,
  new_status        VARCHAR(30) DEFAULT NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_actions_alert (alert_id),
  KEY idx_actions_created (created_at),
  CONSTRAINT fk_actions_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
  CONSTRAINT fk_actions_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mitigation_recommendations (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  alert_id          BIGINT UNSIGNED NOT NULL,
  recommendation    VARCHAR(255) NOT NULL,
  action_type       ENUM('rate_limit','isolate_source','block_ip','revoke_mqtt_client','notify_biomed','force_reauth','manual_review') DEFAULT NULL,
  target            VARCHAR(100) DEFAULT NULL,
  is_automatable    BOOLEAN NOT NULL DEFAULT FALSE,
  requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
  applied           BOOLEAN NOT NULL DEFAULT FALSE,
  applied_by        BIGINT UNSIGNED DEFAULT NULL,
  applied_at        DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_mitigation_alert (alert_id),
  CONSTRAINT fk_mitigation_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
  CONSTRAINT fk_mitigation_user FOREIGN KEY (applied_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notifications (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  alert_id       BIGINT UNSIGNED NOT NULL,
  channel        ENUM('email','sms','telegram','webhook','websocket') NOT NULL,
  recipient      VARCHAR(150) DEFAULT NULL,
  payload        JSON DEFAULT NULL,
  status         ENUM('pending','sent','failed') NOT NULL DEFAULT 'pending',
  retry_count    TINYINT NOT NULL DEFAULT 0,
  error_message  VARCHAR(255) DEFAULT NULL,
  sent_at        DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_notifications_alert (alert_id),
  CONSTRAINT fk_notifications_alert FOREIGN KEY (alert_id) REFERENCES alerts(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blocklist (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entry_type   ENUM('ip','mac','mqtt_client') NOT NULL,
  value        VARCHAR(100) NOT NULL,
  reason       VARCHAR(255) DEFAULT NULL,
  alert_id     BIGINT UNSIGNED DEFAULT NULL,
  added_by     BIGINT UNSIGNED DEFAULT NULL,
  expires_at   DATETIME DEFAULT NULL,
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_blocklist_value (value),
  CONSTRAINT fk_blocklist_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
  CONSTRAINT fk_blocklist_user FOREIGN KEY (added_by) REFERENCES users(id)
) ENGINE=InnoDB;

-- ============================================================================
-- G. SYSTEM
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_config (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  config_key    VARCHAR(80) NOT NULL,
  config_value  VARCHAR(255) DEFAULT NULL,
  value_type    ENUM('string','int','float','bool','json') NOT NULL DEFAULT 'string',
  description   VARCHAR(255) DEFAULT NULL,
  updated_by    BIGINT UNSIGNED DEFAULT NULL,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_config_key (config_key),
  CONSTRAINT fk_config_user FOREIGN KEY (updated_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS thresholds (
  id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  scope              ENUM('global','device_type','device','patient') NOT NULL,
  scope_id           BIGINT UNSIGNED DEFAULT NULL,
  metric             VARCHAR(50) NOT NULL,
  min_value          DECIMAL(12,4) DEFAULT NULL,
  max_value          DECIMAL(12,4) DEFAULT NULL,
  max_delta_per_sec  DECIMAL(12,4) DEFAULT NULL,
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  KEY idx_thresholds_scope (scope, scope_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS reports (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  report_type    ENUM('daily','weekly','incident','compliance','custom','patient','device','ward') NOT NULL,
  title          VARCHAR(200) DEFAULT NULL,
  period_start   DATETIME DEFAULT NULL,
  period_end     DATETIME DEFAULT NULL,
  filters        JSON DEFAULT NULL,
  summary_stats  JSON DEFAULT NULL,
  file_path      VARCHAR(255) DEFAULT NULL,
  generated_by   BIGINT UNSIGNED DEFAULT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_reports_user FOREIGN KEY (generated_by) REFERENCES users(id)
) ENGINE=InnoDB;

-- ==========================================================================
-- REFERENCE AND DEMO DATA
-- ==========================================================================
--
-- Everything below is data, not structure. A fresh install needs it to be
-- usable: the roles permissions are checked against, the ward and device-type
-- catalogues, a demo estate of 10 devices and 5 patients, and the registry of
-- trained models with the metrics the Models page reads.
--
-- Deliberately NOT included:
--   users         password hashes do not belong in a committed file. Register
--                 the first account through the API and it is made an admin,
--                 because it is the first — see services/auth_service.py.
--   detections,   development noise. The Attack Simulator regenerates these in
--   alerts,       seconds; shipping them would put invented incidents into
--   audit_logs    every report a new install produces.
--
-- Safe to re-run: every row is INSERT ... ON DUPLICATE KEY UPDATE id=id, which
-- leaves an existing row untouched rather than failing or overwriting it.
--
-- Regenerate after changing the reference data:
--   python scripts/generate_seed_sql.py

-- roles (4 rows — reference)
INSERT INTO `roles` (`id`, `name`, `description`, `permissions`, `created_at`) VALUES
  (1, 'admin', 'Full system access — user management, model lifecycle, system configuration.', '["alerts.read", "alerts.ack", "alerts.resolve", "alerts.assign", "alerts.comment", "devices.read", "devices.write", "devices.quarantine", "patients.read", "patients.write", "models.read", "models.retrain", "models.activate", "users.manage", "system_config.write", "vitals.read", "vitals.write", "reports.read", "reports.generate"]', '2026-08-02 14:23:49'),
  (2, 'security_analyst', 'IT Security — triages and resolves alerts, manages device response actions.', '["alerts.read", "alerts.ack", "alerts.resolve", "alerts.assign", "alerts.comment", "devices.read", "devices.quarantine", "patients.read", "models.read", "vitals.read", "reports.read", "reports.generate"]', '2026-08-02 14:23:49'),
  (3, 'clinician', 'ICU / ward staff — views vitals and alerts for their patients'' devices only.', '["alerts.read", "devices.read", "patients.read", "patients.write", "vitals.read"]', '2026-08-02 14:23:49'),
  (4, 'viewer', 'Read-only access — dashboard, devices, alerts, reports. Cannot act on anything.', '["alerts.read", "devices.read", "models.read", "vitals.read", "reports.read"]', '2026-08-02 14:23:49')
ON DUPLICATE KEY UPDATE id=id;

-- wards (5 rows — reference)
INSERT INTO `wards` (`id`, `name`, `floor`, `network_segment`, `criticality`) VALUES
  (1, 'ICU-1', '3', '192.168.20.0/24', 'critical'),
  (2, 'ICU-2', '3', '192.168.21.0/24', 'critical'),
  (3, 'Emergency', '0', '192.168.10.0/24', 'high'),
  (4, 'General Ward A', '1', '192.168.30.0/24', 'medium'),
  (5, 'General Ward B', '2', '192.168.31.0/24', 'medium')
ON DUPLICATE KEY UPDATE id=id;

-- device_types (7 rows — reference)
INSERT INTO `device_types` (`id`, `type_name`, `category`, `is_life_critical`, `default_protocols`, `expected_data_rate_kbps`) VALUES
  (1, 'Patient Monitor', 'sensor', 1, '["MQTT", "TCP"]', 12),
  (2, 'Infusion Pump', 'actuator', 1, '["MQTT"]', 4),
  (3, 'Ventilator', 'actuator', 1, '["MQTT", "TCP"]', 20),
  (4, 'Pulse Oximeter', 'sensor', 0, '["BLE", "MQTT"]', 2),
  (5, 'ECG Sensor', 'sensor', 0, '["BLE", "MQTT"]', 8),
  (6, 'Smart Bed', 'hybrid', 0, '["MQTT", "HTTP"]', 3),
  (7, 'Bedside Gateway', 'gateway', 0, '["MQTT", "TCP", "HTTP"]', 50)
ON DUPLICATE KEY UPDATE id=id;

-- attack_types (2 rows — reference)
INSERT INTO `attack_types` (`id`, `code`, `family`, `display_name`, `description`, `default_severity`, `mitre_technique`, `typical_indicators`, `recommended_action`) VALUES
  (1, 'DATA_ALTERATION', 'SPOOFING', 'Data Alteration (MITM)', 'Attacker intercepts and rewrites patient vitals in transit (e.g. SpO2, heart rate) before they reach the monitoring backend.', 'critical', 'T1565', '["implausible vitals", "jumpy values inconsistent with physiology", "MITM position on segment"]', 'Cross-check vitals against a redundant sensor if available; investigate MITM position on the network segment. Never auto-disconnect a life-critical device.'),
  (2, 'SPOOFING_MITM', 'SPOOFING', 'Spoofing (ARP/MITM)', 'ARP or IP spoofing used to position an attacker as a man-in-the-middle between an IoMT device and the gateway.', 'high', 'T1557', '["TTL anomalies", "MAC/IP binding mismatch", "duplicate ARP replies"]', 'Verify MAC/IP bindings against the device registry; isolate the suspected attacker host at the switch/gateway.')
ON DUPLICATE KEY UPDATE id=id;

-- datasets (1 rows — reference)
INSERT INTO `datasets` (`id`, `name`, `version`, `source_url`, `total_records`, `num_features`, `num_classes`, `benign_ratio`, `citation`, `notes`) VALUES
  (1, 'WUSTL-EHMS-2020', '2020', 'https://www.cse.wustl.edu/~jain/ehms/index.html', 16318, 44, 2, 0.8746, 'A. A. Hady, A. Ghubaish, T. Salman, D. Unal, R. Jain, "Intrusion Detection System for Healthcare Systems Using Medical and Network Data: A Comparison Study," IEEE Access, 2020.', 'EHMS testbed. 35 network-flow + 8 patient-biometric features + 1 label. Attacks: MITM spoofing and data injection/alteration.')
ON DUPLICATE KEY UPDATE id=id;

-- devices (10 rows — demo estate)
INSERT INTO `devices` (`id`, `device_uid`, `device_type_id`, `ward_id`, `manufacturer`, `model_number`, `firmware_version`, `ip_address`, `mac_address`, `registered_mac_ip_binding`, `mqtt_client_id`, `status`, `trust_score`, `last_seen_at`, `quarantined_until`, `created_at`, `updated_at`) VALUES
  (3, 'MON-ICU1-001', 1, 1, 'Philips', 'IntelliVue MX450', 'J.10.11', '192.168.20.11', '84:3A:4B:0F:5B:94', '84:3A:4B:0F:5B:94|192.168.20.11', 'mon-icu1-001', 'online', 100, '2026-08-05 17:36:06', NULL, '2026-08-05 23:06:06', '2026-09-06 12:46:42'),
  (4, 'PUMP-ICU1-002', 2, 1, 'B. Braun', 'Infusomat Space', '2.3.1', '192.168.20.12', 'B8:CA:3A:CF:0B:87', 'B8:CA:3A:CF:0B:87|192.168.20.12', 'pump-icu1-002', 'online', 100, '2026-08-05 17:36:06', NULL, '2026-08-05 23:06:06', '2026-08-05 23:06:06'),
  (5, 'VENT-ICU1-003', 3, 1, 'Drager', 'Evita V500', '3.10', '192.168.20.13', '00:1B:44:11:3A:B7', '00:1B:44:11:3A:B7|192.168.20.13', 'vent-icu1-003', 'online', 100, '2026-08-05 17:36:06', NULL, '2026-08-05 23:06:06', '2026-08-05 23:06:06'),
  (6, 'MON-ICU2-001', 1, 2, 'Philips', 'IntelliVue MX450', 'J.10.11', '192.168.21.11', '84:3A:4B:0F:5C:21', '84:3A:4B:0F:5C:21|192.168.21.11', 'mon-icu2-001', 'online', 100, '2026-08-05 17:36:06', NULL, '2026-08-05 23:06:06', '2026-08-05 23:06:06'),
  (7, 'PULSEOX-GWA-001', 4, 4, 'Nonin', 'WristOx2 3150', '1.4', '192.168.30.15', 'A4:C1:38:6D:2F:19', 'A4:C1:38:6D:2F:19|192.168.30.15', 'pulseox-gwa-001', 'online', 100, '2026-08-05 17:36:07', NULL, '2026-08-05 23:06:07', '2026-09-06 12:42:55'),
  (8, 'ECG-GWA-002', 5, 4, 'GE Healthcare', 'CardioLab', '2.1', '192.168.30.16', '5C:F9:38:AA:11:02', '5C:F9:38:AA:11:02|192.168.30.16', 'ecg-gwa-002', 'offline', 100, NULL, NULL, '2026-08-05 23:06:07', '2026-08-05 23:06:07'),
  (9, 'BED-GWB-001', 6, 5, 'Hillrom', 'Centrella', '4.0', '192.168.31.20', '2C:33:7A:90:4D:11', '2C:33:7A:90:4D:11|192.168.31.20', 'bed-gwb-001', 'online', 100, '2026-08-05 17:36:07', NULL, '2026-08-05 23:06:07', '2026-08-05 23:06:07'),
  (10, 'GATE-EMRG-001', 7, 3, 'Cisco', 'IR1101', '17.9', '192.168.10.5', '00:1A:2B:3C:4D:5E', '00:1A:2B:3C:4D:5E|192.168.10.5', 'gate-emrg-001', 'online', 100, '2026-08-05 17:36:07', NULL, '2026-08-05 23:06:07', '2026-08-05 23:06:07'),
  (11, 'MON-EMRG-002', 1, 3, 'Mindray', 'ePM 12', '5.2', '192.168.10.12', '94:DE:80:1F:6B:33', '94:DE:80:1F:6B:33|192.168.10.12', 'mon-emrg-002', 'quarantined', 100, NULL, NULL, '2026-08-05 23:06:07', '2026-08-05 23:06:07'),
  (12, 'PUMP-GWB-003', 2, 5, 'B. Braun', 'Infusomat Space', '2.3.1', '192.168.31.22', 'B8:CA:3A:CF:0C:44', 'B8:CA:3A:CF:0C:44|192.168.31.22', 'pump-gwb-003', 'maintenance', 100, NULL, NULL, '2026-08-05 23:06:07', '2026-08-05 23:06:07')
ON DUPLICATE KEY UPDATE id=id;

-- patients (5 rows — demo estate)
INSERT INTO `patients` (`id`, `patient_code`, `age_band`, `sex`, `ward_id`, `admitted_at`, `discharged_at`, `baseline_hr_min`, `baseline_hr_max`, `baseline_spo2_min`, `notes`) VALUES
  (1, 'PT-0001', '60-69', 'M', 1, '2026-08-05 17:42:25', NULL, 60, 100, 94, 'Post-op cardiac monitoring'),
  (2, 'PT-0002', '70-79', 'F', 2, '2026-08-05 17:42:25', NULL, 55, 95, 92, 'Respiratory distress observation'),
  (3, 'PT-0003', '40-49', 'M', 4, '2026-08-05 17:42:25', NULL, 60, 100, 95, 'Routine recovery monitoring'),
  (4, 'PT-0004', '30-39', 'F', 3, '2026-08-05 17:42:25', NULL, 60, 110, 93, 'Triage - under observation'),
  (5, 'PT-0005', '80-89', 'O', 5, '2026-08-05 17:42:25', NULL, 55, 90, 93, 'Long-term care')
ON DUPLICATE KEY UPDATE id=id;

-- patient_device_assignments (6 rows — demo estate)
INSERT INTO `patient_device_assignments` (`id`, `patient_id`, `device_id`, `assigned_at`, `released_at`) VALUES
  (1, 1, 3, '2026-08-05 17:42:25', NULL),
  (2, 1, 5, '2026-08-05 17:42:25', NULL),
  (3, 2, 6, '2026-08-05 17:42:25', NULL),
  (4, 3, 7, '2026-08-05 17:42:25', NULL),
  (5, 4, 11, '2026-08-05 17:42:25', NULL),
  (6, 5, 9, '2026-08-05 17:42:25', NULL)
ON DUPLICATE KEY UPDATE id=id;

-- ml_models (10 rows — trained model registry)
INSERT INTO `ml_models` (`id`, `model_code`, `display_name`, `stage`, `algorithm`, `task_type`, `version`, `artifact_path`, `scaler_path`, `feature_set_version`, `hyperparameters`, `input_dim`, `output_classes`, `threshold`, `is_active`, `trained_at`, `trained_by`, `created_at`) VALUES
  (1, 'M1_RF_BINARY_WUSTL', 'M1 Random Forest (Stage 1)', 1, 'RandomForest', 'binary', 'v1.0.0', 'models/binary_rf_v1.pkl', 'data/scalers/scaler_v1.pkl', 'v1', '{"n_estimators": 200, "max_depth": 25, "min_samples_split": 5, "min_samples_leaf": 2, "max_features": "sqrt", "class_weight": "balanced_subsample"}', 44, 'null', 0.5, 1, '2026-08-05 16:51:39', NULL, '2026-08-05 22:21:39'),
  (2, 'M2_XGB_MULTICLASS_WUSTL', 'XGBoost (Multiclass, Stage 2) - WUSTL-EHMS-2020', 2, 'XGBoost', 'multiclass', 'v1.0.0', 'models/multiclass_xgb_v1.pkl', 'data/scalers/scaler_v1.pkl', 'v1', '{"objective": "multi:softprob", "num_class": 3, "n_estimators": 400, "max_depth": 8, "learning_rate": 0.08, "subsample": 0.85, "colsample_bytree": 0.85}', 44, '["Data Alteration", "Spoofing", "normal"]', 0.6, 1, '2026-08-05 17:13:38', NULL, '2026-08-05 22:43:38'),
  (3, 'M4_AUTOENCODER_WUSTL', 'Deep Autoencoder (Zero-day, Stage 3) - WUSTL-EHMS-2020', 3, 'Autoencoder', 'anomaly', 'v1.0.0', 'models/autoencoder_v1.keras', 'data/scalers/scaler_v1.pkl', 'v1', '{"architecture": "44-32-16-8-4-8-16-32-44", "loss": "mse", "optimizer": "adam", "lr": 0.001, "percentile": 97.5, "trained_on": "benign-only"}', 44, 'null', 0.3376, 1, '2026-08-05 17:23:30', NULL, '2026-08-05 22:53:30'),
  (4, 'VITALS_LSTM_V1', 'Vitals LSTM Forecaster (Stage 4)', 4, 'LSTM', 'regression', 'v1', 'models/vitals_lstm_v1.keras', 'data/scalers/vitals_scaler_v1.pkl', NULL, NULL, 6, NULL, 3, 1, NULL, NULL, '2026-09-06 12:34:06'),
  (5, 'M2_XGB_BINARY_WUSTL', 'M2 XGBoost (Stage 1 alternate)', NULL, 'XGBoost', 'binary', 'v1', 'models/binary_xgb_v1.pkl', 'data/scalers/scaler_v1.pkl', 'v1', NULL, NULL, NULL, NULL, 0, '2026-09-06 08:28:38', NULL, '2026-09-06 13:58:38'),
  (6, 'M5_IFOREST_WUSTL', 'M5 Isolation Forest (Stage 3 companion)', NULL, 'IsolationForest', 'anomaly', 'v1', 'models/isolation_forest_v1.pkl', 'data/scalers/scaler_v1.pkl', 'v1', NULL, NULL, NULL, NULL, 0, '2026-09-06 08:28:38', NULL, '2026-09-06 13:58:38'),
  (7, 'M7_OCSVM_WUSTL', 'M7 One-Class SVM (Stage 3 baseline)', NULL, 'OneClassSVM', 'anomaly', 'v1', 'models/one_class_svm_v1.pkl', 'data/scalers/scaler_v1.pkl', 'v1', NULL, NULL, NULL, NULL, 0, '2026-09-06 08:28:38', NULL, '2026-09-06 13:58:38'),
  (8, 'M8_LOGREG_WUSTL', 'M8 Logistic Regression (baseline)', NULL, 'LogisticRegression', 'binary', 'v1', '(not deployed — see models/binary_results.json)', 'data/scalers/scaler_v1.pkl', 'v1', NULL, NULL, NULL, NULL, 0, '2026-09-06 08:28:38', NULL, '2026-09-06 13:58:38'),
  (9, 'M9_SVM_RBF_WUSTL', 'M9 SVM-RBF (baseline)', NULL, 'SVC-RBF', 'binary', 'v1', '(not deployed — see models/binary_results.json)', 'data/scalers/scaler_v1.pkl', 'v1', NULL, NULL, NULL, NULL, 0, '2026-09-06 08:28:38', NULL, '2026-09-06 13:58:38'),
  (10, 'M10_STACKING_WUSTL', 'M10 Stacking Ensemble', NULL, 'LogisticRegression-meta', 'meta', 'v1', 'models/stacking_meta_v1.pkl', 'data/scalers/scaler_v1.pkl', 'v1', NULL, NULL, NULL, NULL, 0, '2026-09-06 08:28:38', NULL, '2026-09-06 13:58:38')
ON DUPLICATE KEY UPDATE id=id;

-- training_runs (7 rows — trained model registry)
INSERT INTO `training_runs` (`id`, `model_id`, `dataset_id`, `run_uid`, `train_size`, `val_size`, `test_size`, `resampling_method`, `epochs`, `batch_size`, `duration_seconds`, `hardware`, `status`, `loss_curve`, `notes`, `started_at`, `finished_at`) VALUES
  (1, 1, 1, '9a9c918c-b500-52ae-81b3-3eb51769ac96', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:36'),
  (2, 5, 1, 'e98b2650-96ec-5043-8c90-a51ac899cd1a', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:38'),
  (3, 6, 1, 'e8b524bb-435a-564a-ab59-d2eb4cafaf1d', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:38'),
  (4, 7, 1, 'ca873b95-f23b-5ce2-8925-24fab744a066', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:38'),
  (5, 8, 1, '941231c7-4e15-533b-8726-5bd0d0eca6dc', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:38'),
  (6, 9, 1, '21708ee7-da7e-5e05-9861-7a16a27eb84a', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:38'),
  (7, 10, 1, 'f436b00d-0ccf-59e3-864b-2eb0568ea097', NULL, NULL, NULL, 'SMOTE (training split only)', NULL, NULL, NULL, NULL, 'completed', NULL, 'registered by backend/register_models.py from the ml/ results files', NULL, '2026-09-06 08:28:38')
ON DUPLICATE KEY UPDATE id=id;

-- model_metrics (7 rows — trained model registry)
INSERT INTO `model_metrics` (`id`, `training_run_id`, `split`, `class_label`, `accuracy`, `precision`, `recall`, `f1_score`, `roc_auc`, `pr_auc`, `false_positive_rate`, `false_negative_rate`, `support`, `confusion_matrix`, `avg_inference_ms`, `created_at`) VALUES
  (8, 1, 'test', NULL, 0.930964, 0.691667, 0.811075, 0.746627, 0.950528, NULL, 0.051845, NULL, NULL, '[[2030, 111], [58, 249]]', 0.02, '2026-09-06 14:06:09'),
  (9, 2, 'test', NULL, 0.972222, 0.861027, 0.928339, 0.893417, 0.991651, NULL, 0.021485, NULL, NULL, '[[2095, 46], [22, 285]]', NULL, '2026-09-06 14:06:09'),
  (10, 3, 'test', NULL, NULL, 0.733333, 0.501629, 0.595745, 0.721921, NULL, 0.026156, NULL, NULL, '[[2085, 56], [153, 154]]', 0.065, '2026-09-06 14:06:09'),
  (11, 4, 'test', NULL, NULL, 0.778723, 0.596091, 0.675277, 0.744824, NULL, 0.024288, NULL, NULL, '[[2089, 52], [124, 183]]', 0.032, '2026-09-06 14:06:09'),
  (12, 5, 'test', NULL, 0.879085, 0.514066, 0.654723, 0.575931, 0.876291, NULL, 0.088744, NULL, NULL, '[[1951, 190], [106, 201]]', 0, '2026-09-06 14:06:09'),
  (13, 6, 'test', NULL, 0.906046, 0.598465, 0.762215, 0.670487, 0.930443, NULL, 0.07333, NULL, NULL, '[[1984, 157], [73, 234]]', 0.493, '2026-09-06 14:06:09'),
  (14, 7, 'test', NULL, 0.962418, 0.792916, 0.947883, 0.863501, 0.990999, NULL, 0.035497, NULL, NULL, '[[2065, 76], [16, 291]]', NULL, '2026-09-06 14:06:09')
ON DUPLICATE KEY UPDATE id=id;

-- feature_importances (50 rows — trained model registry)
INSERT INTO `feature_importances` (`id`, `model_id`, `feature_name`, `importance_gain`, `shap_mean_abs`, `rank`) VALUES
  (51, 1, 'DIntPkt', 0.11966019, NULL, 1),
  (52, 1, 'DstJitter', 0.10924377, NULL, 2),
  (53, 1, 'Flgs_ e', 0.08624739, NULL, 3),
  (54, 1, 'Sport', 0.07724839, NULL, 4),
  (55, 1, 'SIntPkt', 0.0766082, NULL, 5),
  (56, 1, 'Temp', 0.05440561, NULL, 6),
  (57, 1, 'Dur', 0.04779102, NULL, 7),
  (58, 1, 'DstLoad', 0.04762846, NULL, 8),
  (59, 1, 'SrcJitter', 0.04355262, NULL, 9),
  (60, 1, 'SrcLoad', 0.04277857, NULL, 10),
  (61, 1, 'Flgs_ M', 0.04267405, NULL, 11),
  (62, 1, 'Load', 0.04022235, NULL, 12),
  (63, 1, 'Rate', 0.03925034, NULL, 13),
  (64, 1, 'Pulse_Rate', 0.03182225, NULL, 14),
  (65, 1, 'Resp_Rate', 0.02664105, NULL, 15),
  (66, 1, 'Heart_rate', 0.02491968, NULL, 16),
  (67, 1, 'ST', 0.02480042, NULL, 17),
  (68, 1, 'Flgs_ eR', 0.01848198, NULL, 18),
  (69, 1, 'SYS', 0.01577091, NULL, 19),
  (70, 1, 'SpO2', 0.01570552, NULL, 20),
  (71, 1, 'DIA', 0.01407237, NULL, 21),
  (72, 1, 'Flgs_ e s', 0.00024211, NULL, 22),
  (73, 1, 'Flgs_ M *', 0.00022417, NULL, 23),
  (74, 1, 'Flgs_ M d', 0.00000859, NULL, 24),
  (75, 1, 'Dport', 0, NULL, 25),
  (76, 5, 'Flgs_ e', 0.61426091, NULL, 1),
  (77, 5, 'Flgs_ M', 0.07835332, NULL, 2),
  (78, 5, 'Flgs_ eR', 0.04055369, NULL, 3),
  (79, 5, 'Rate', 0.03030161, NULL, 4),
  (80, 5, 'DIntPkt', 0.02951688, NULL, 5),
  (81, 5, 'DstJitter', 0.02659712, NULL, 6),
  (82, 5, 'Flgs_ M *', 0.01989654, NULL, 7),
  (83, 5, 'SpO2', 0.01605789, NULL, 8),
  (84, 5, 'Flgs_ e s', 0.01538801, NULL, 9),
  (85, 5, 'Sport', 0.01503146, NULL, 10),
  (86, 5, 'Temp', 0.01418551, NULL, 11),
  (87, 5, 'Pulse_Rate', 0.01374374, NULL, 12),
  (88, 5, 'Resp_Rate', 0.01241948, NULL, 13),
  (89, 5, 'Load', 0.01130546, NULL, 14),
  (90, 5, 'ST', 0.00993905, NULL, 15),
  (91, 5, 'Heart_rate', 0.00957855, NULL, 16),
  (92, 5, 'SYS', 0.0092428, NULL, 17),
  (93, 5, 'SrcJitter', 0.00750658, NULL, 18),
  (94, 5, 'DIA', 0.00657952, NULL, 19),
  (95, 5, 'SIntPkt', 0.00567644, NULL, 20),
  (96, 5, 'DstLoad', 0.00543502, NULL, 21),
  (97, 5, 'Dur', 0.00433986, NULL, 22),
  (98, 5, 'SrcLoad', 0.00382755, NULL, 23),
  (99, 5, 'Flgs_ M d', 0.00026307, NULL, 24),
  (100, 5, 'Dport', 0, NULL, 25)
ON DUPLICATE KEY UPDATE id=id;


SET FOREIGN_KEY_CHECKS = 1;
