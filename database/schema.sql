-- ============================================================================
-- AI-Based Cyber Attack Detection in the IoMT — Complete Database Schema
-- Engine: MySQL 8.0, InnoDB, utf8mb4_unicode_ci
-- Source: docs/IoMT_Attack_Detection_Build_Document.pdf, Section 10
-- Run: mysql -u root -p < database/schema.sql
-- ============================================================================

CREATE DATABASE IF NOT EXISTS iomt_ids
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE iomt_ids;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- A. IDENTITY & ACCESS
-- ============================================================================

CREATE TABLE roles (
  id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(50)  NOT NULL,
  description VARCHAR(255) DEFAULT NULL,
  permissions JSON NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_roles_name (name)
) ENGINE=InnoDB;

CREATE TABLE users (
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

CREATE TABLE user_sessions (
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

CREATE TABLE audit_logs (
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

CREATE TABLE wards (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name            VARCHAR(100) NOT NULL,
  floor           VARCHAR(20) DEFAULT NULL,
  network_segment VARCHAR(50) DEFAULT NULL,
  criticality     ENUM('low','medium','high','critical') NOT NULL DEFAULT 'medium',
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE device_types (
  id                      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  type_name               VARCHAR(100) NOT NULL,
  category                ENUM('sensor','actuator','gateway','hybrid') NOT NULL,
  is_life_critical        BOOLEAN NOT NULL DEFAULT FALSE,
  default_protocols       JSON DEFAULT NULL,
  expected_data_rate_kbps DECIMAL(8,2) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_device_type_name (type_name)
) ENGINE=InnoDB;

CREATE TABLE devices (
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

CREATE TABLE device_profiles (
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

CREATE TABLE patients (
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

CREATE TABLE patient_device_assignments (
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

CREATE TABLE datasets (
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

CREATE TABLE attack_types (
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

CREATE TABLE protocols (
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

CREATE TABLE vital_readings (
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

CREATE TABLE network_flows (
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

CREATE TABLE flow_features (
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

CREATE TABLE ml_models (
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

CREATE TABLE training_runs (
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

CREATE TABLE model_metrics (
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

CREATE TABLE feature_importances (
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

CREATE TABLE detections (
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

CREATE TABLE explanations (
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

CREATE TABLE alerts (
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

CREATE TABLE alert_actions (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  alert_id          BIGINT UNSIGNED NOT NULL,
  user_id           BIGINT UNSIGNED DEFAULT NULL,
  action            ENUM('created','acknowledged','assigned','commented','escalated','mitigated','resolved','marked_false_positive','reopened') NOT NULL,
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

CREATE TABLE mitigation_recommendations (
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

CREATE TABLE notifications (
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

CREATE TABLE blocklist (
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

CREATE TABLE system_config (
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

CREATE TABLE thresholds (
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

CREATE TABLE reports (
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

SET FOREIGN_KEY_CHECKS = 1;
