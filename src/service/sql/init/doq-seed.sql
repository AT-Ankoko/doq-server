-- TryAngle seed scaffold

START TRANSACTION;

-- TODO: seed required base data
-- Example:
-- INSERT INTO tb_img_ctg (id, name, cDate, uDate)
-- VALUES ('ctg-default', 'default', 0, 0);

-- 참고: 현재 시드는 빈 DB에서 최초 실행되어 AUTO_INCREMENT 값이 1부터 순차 증가하는 것을 전제로 합니다.

-- 1. 사용자 시드 데이터
INSERT INTO tb_user (email, password, name, nickname, phone, emailConf, `desc`, role, cDate, uDate) VALUES
('2025tryangle@gmail.com', '$pbkdf2-sha256$29000$SmlNCYGQktI6R.idc.699w$iTbohqKsrbnrNkebpBY8BR2mPGc95ffLQ/j0WrfFKKA', '트라이앵글', '슈퍼어드민', '010-0000-0000', '1', '시스템 최고 관리자입니다.', 'SUPER_ADMIN', 1712966400, 1712966400),
('admin@email.com', '$pbkdf2-sha256$29000$OAcAwLiXUkrpXYsxBgBgTA$gHlq3/zq1jPN7H8qp5bJ5dzvs/Kru9zKgd0yDRn9d1k', '트라이앵글어드민', '관리자', '010-1111-1111', '1', '서비스 운영 관리자입니다.', 'ADMIN', 1712966400, 1712966400),
('guest@email.com', '$pbkdf2-sha256$29000$9V4L4RyDkBLCWGtNqTXmPA$Nm4eoUup./ecGYMV4CUqQTur4rXIjjMyURnubaFQ0gs', '김예공', '게스트', '010-2222-2222', '1', '일반 사용자입니다.', 'CLIENT', 1712966400, 1712966400);

-- 2. 이미지 카테고리 시드 데이터
INSERT INTO tb_img_ctg (name, cDate, uDate) VALUES
('전신', 1712966400, 1712966400),
('상체 중심', 1712966400, 1712966400),
('하체 중심', 1712966400, 1712966400),
('셀카', 1712966400, 1712966400),
('내찍사', 1712966400, 1712966400),
('남찍사', 1712966400, 1712966400);

COMMIT;