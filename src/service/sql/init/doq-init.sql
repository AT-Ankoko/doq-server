-- TryAngle initial schema
-- Target: MySQL 8.0+ (utf8mb4)

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

CREATE TABLE IF NOT EXISTS tb_user (
	id BIGINT NOT NULL AUTO_INCREMENT,
	email VARCHAR(255) NOT NULL,
	password VARCHAR(255) NULL,
	name VARCHAR(100) NULL,
	nickname VARCHAR(100) NULL,
	phone VARCHAR(20) NULL,
	emailConf VARCHAR(1) NOT NULL DEFAULT '2',
	`desc` TEXT NULL,
	fileId VARCHAR(255) NULL,
	role ENUM('SUPER_ADMIN', 'ADMIN', 'CLIENT') NOT NULL DEFAULT 'CLIENT',
	state INT NOT NULL DEFAULT 1,
	extra JSON NULL,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE KEY uk_tb_user_email (email),
	KEY idx_tb_user_state (state),
	CONSTRAINT ck_tb_user_state CHECK (state IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_img_ctg (
	id BIGINT NOT NULL AUTO_INCREMENT,
	name VARCHAR(100) NOT NULL,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_tag (
	id BIGINT NOT NULL AUTO_INCREMENT,
	userId BIGINT NOT NULL,
	parentCode VARCHAR(50) NULL,
	code VARCHAR(50) NOT NULL,
	tagName VARCHAR(100) NOT NULL,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE KEY uk_tb_tag_code (code),
	KEY idx_tb_tag_userId (userId),
	CONSTRAINT fk_tb_tag_userId FOREIGN KEY (userId) REFERENCES tb_user (id)
		ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_img (
	id BIGINT NOT NULL AUTO_INCREMENT,
	userId BIGINT NOT NULL,
	ctgId BIGINT NOT NULL,
	imgUrl VARCHAR(500) NOT NULL,
	title VARCHAR(200) NULL,
	`desc` TEXT NULL,
	useCnt INT NOT NULL DEFAULT 0,
	kwd JSON NULL,
	aiDoc JSON NULL,
	expWeight FLOAT NOT NULL DEFAULT 0,
	pri INT NOT NULL DEFAULT 0,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	KEY idx_tb_img_userId (userId),
	KEY idx_tb_img_ctgId (ctgId),
	KEY idx_tb_img_rank (useCnt, expWeight, pri),
	CONSTRAINT fk_tb_img_userId FOREIGN KEY (userId) REFERENCES tb_user (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_tb_img_ctgId FOREIGN KEY (ctgId) REFERENCES tb_img_ctg (id)
		ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_session (
	id VARCHAR(32) NOT NULL,
	userId BIGINT NOT NULL,
	imgId BIGINT NOT NULL,
	sDate BIGINT NOT NULL,
	eDate BIGINT NULL,
	device JSON NULL,
	sStat INT NOT NULL DEFAULT 0,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	KEY idx_tb_session_userId (userId),
	KEY idx_tb_session_imgId (imgId),
	KEY idx_tb_session_status_date (sStat, sDate),
	CONSTRAINT fk_tb_session_userId FOREIGN KEY (userId) REFERENCES tb_user (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_tb_session_imgId FOREIGN KEY (imgId) REFERENCES tb_img (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT ck_tb_session_sStat CHECK (sStat IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_prod (
	id BIGINT NOT NULL AUTO_INCREMENT,
	userId BIGINT NOT NULL,
	name VARCHAR(200) NOT NULL,
	brand VARCHAR(300) NULL,
	price INT NOT NULL DEFAULT 0,
	thumbUrl VARCHAR(500) NULL,
	pStat INT NOT NULL DEFAULT 1,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	KEY idx_tb_prod_userId (userId),
	KEY idx_tb_prod_pStat (pStat),
	CONSTRAINT fk_tb_prod_userId FOREIGN KEY (userId) REFERENCES tb_user (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT ck_tb_prod_pStat CHECK (pStat IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_snap (
	id BIGINT NOT NULL AUTO_INCREMENT,
	userId BIGINT NOT NULL,
	prodId BIGINT NOT NULL,
	imgId BIGINT NOT NULL,
	sId VARCHAR(32) NULL,
	snapUrl VARCHAR(500) NOT NULL,
	comment TEXT NULL,
	gender INT NOT NULL DEFAULT 0,
	userH FLOAT NULL,
	userW FLOAT NULL,
	viewCnt INT NOT NULL DEFAULT 0,
	cDate BIGINT NOT NULL,
	uDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	KEY idx_tb_snap_userId (userId),
	KEY idx_tb_snap_prodId (prodId),
	KEY idx_tb_snap_imgId (imgId),
	UNIQUE KEY uk_tb_snap_sId (sId),
	KEY idx_tb_snap_viewCnt (viewCnt),
	CONSTRAINT fk_tb_snap_userId FOREIGN KEY (userId) REFERENCES tb_user (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_tb_snap_prodId FOREIGN KEY (prodId) REFERENCES tb_prod (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_tb_snap_imgId FOREIGN KEY (imgId) REFERENCES tb_img (id)
		ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_tb_snap_sId FOREIGN KEY (sId) REFERENCES tb_session (id)
		ON DELETE SET NULL ON UPDATE CASCADE,
	CONSTRAINT ck_tb_snap_gender CHECK (gender IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_rt_snapshot (
    id BIGINT NOT NULL AUTO_INCREMENT,
    sId VARCHAR(32) NOT NULL,
    secSeq INT NOT NULL,
    sDate BIGINT NOT NULL,
    eDate BIGINT NOT NULL,
    rawPayload JSON NOT NULL,
    cDate BIGINT NOT NULL,
    
    -- 1. 기존 가상 컬럼 (유저 ID 추출)
    userId BIGINT GENERATED ALWAYS AS (
        CAST(JSON_UNQUOTE(JSON_EXTRACT(rawPayload, '$.data.session.userId')) AS UNSIGNED)
    ) STORED,

    -- 2. 신규 추가된 비즈니스 가상 컬럼 (샘플 데이터의 실제 JSON 패스 반영)
    category VARCHAR(50) GENERATED ALWAYS AS (
        JSON_UNQUOTE(JSON_EXTRACT(rawPayload, '$.data.snapshots[0].res.category'))
    ) STORED,
    
    feedback VARCHAR(255) GENERATED ALWAYS AS (
        JSON_UNQUOTE(JSON_EXTRACT(rawPayload, '$.data.snapshots[0].res.feedback'))
    ) STORED,
    
    reason TEXT GENERATED ALWAYS AS (
        JSON_UNQUOTE(JSON_EXTRACT(rawPayload, '$.data.snapshots[0].res.metadata.reason'))
    ) STORED,
    
    stuckSec INT GENERATED ALWAYS AS (
        CAST(JSON_EXTRACT(rawPayload, '$.data.snapshots[0].res.metadata.stuckSec') AS UNSIGNED)
    ) STORED,
    
    canCapture VARCHAR(10) GENERATED ALWAYS AS (
        JSON_UNQUOTE(JSON_EXTRACT(rawPayload, '$.data.snapshots[0].res.metadata.canCapture'))
    ) STORED,

    PRIMARY KEY (id, cDate),
    
    -- 기본 인덱스
    KEY idx_rt_snapshot_session_timeline (sId, secSeq, cDate),
    KEY idx_rt_snapshot_user_search (userId, cDate),
    
    -- [신규] 통계 및 모니터링 고속 조회를 위한 복합 인덱스 추가
    -- 촬영 단계별, 캡처 가능 여부별, 정체 시간 조건을 조합한 고속 검색 지원
    KEY idx_rt_snapshot_biz_metrics (category, canCapture, stuckSec),

    CONSTRAINT fk_tb_rt_snapshot_sId FOREIGN KEY (sId) REFERENCES tb_session (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS mtb_bookmark (
	id BIGINT NOT NULL AUTO_INCREMENT,
	userId BIGINT NOT NULL,
	imgId BIGINT NOT NULL,
	cDate BIGINT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE KEY uk_mtb_bookmark_user_img (userId, imgId),
	KEY idx_mtb_bookmark_userId (userId),
	KEY idx_mtb_bookmark_imgId (imgId),
	CONSTRAINT fk_mtb_bookmark_userId FOREIGN KEY (userId) REFERENCES tb_user (id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	CONSTRAINT fk_mtb_bookmark_imgId FOREIGN KEY (imgId) REFERENCES tb_img (id)
		ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS mtb_img_tag (
	id BIGINT NOT NULL AUTO_INCREMENT,
	imgId BIGINT NOT NULL,
	tagId BIGINT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE KEY uk_mtb_img_tag_img_tag (imgId, tagId),
	KEY idx_mtb_img_tag_imgId (imgId),
	KEY idx_mtb_img_tag_tagId (tagId),
	CONSTRAINT fk_mtb_img_tag_imgId FOREIGN KEY (imgId) REFERENCES tb_img (id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	CONSTRAINT fk_mtb_img_tag_tagId FOREIGN KEY (tagId) REFERENCES tb_tag (id)
		ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

COMMIT;

SET FOREIGN_KEY_CHECKS = 1;
