-- Esquema PostgreSQL (la app lo crea sola al arrancar; este archivo es solo de referencia)

CREATE TABLE participants (
	id SERIAL NOT NULL, 
	public_id VARCHAR(32) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	full_name VARCHAR(80) NOT NULL, 
	area VARCHAR(80) NOT NULL, 
	cargo VARCHAR(40) NOT NULL, 
	nivel VARCHAR(20) NOT NULL, 
	consent BOOLEAN NOT NULL, 
	current_step INTEGER NOT NULL, 
	registered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_activity TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_participants_area ON participants (area);

CREATE INDEX ix_participants_last_activity ON participants (last_activity);

CREATE UNIQUE INDEX ix_participants_public_id ON participants (public_id);

CREATE UNIQUE INDEX ix_participants_token_hash ON participants (token_hash);

CREATE TABLE module_progress (
	participant_id INTEGER NOT NULL, 
	step_id VARCHAR(20) NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (participant_id, step_id), 
	FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE CASCADE
);

CREATE INDEX ix_module_progress_step ON module_progress (step_id);

CREATE TABLE participant_state (
	participant_id INTEGER NOT NULL, 
	state_json TEXT NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (participant_id), 
	FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE CASCADE
);

CREATE TABLE result_scores (
	participant_id INTEGER NOT NULL, 
	myths_correct INTEGER NOT NULL, 
	myths_total INTEGER NOT NULL, 
	priv_correct INTEGER NOT NULL, 
	priv_total INTEGER NOT NULL, 
	quiz_correct INTEGER NOT NULL, 
	quiz_total INTEGER NOT NULL, 
	rubric_done INTEGER NOT NULL, 
	PRIMARY KEY (participant_id), 
	FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE CASCADE
);

CREATE TABLE self_assessments (
	participant_id INTEGER NOT NULL, 
	skill_index INTEGER NOT NULL, 
	phase VARCHAR(4) NOT NULL, 
	score INTEGER NOT NULL, 
	PRIMARY KEY (participant_id, skill_index, phase), 
	CONSTRAINT ck_score_range CHECK (score BETWEEN 1 AND 5), 
	CONSTRAINT ck_phase CHECK (phase IN ('pre','post')), 
	CONSTRAINT ck_skill_index CHECK (skill_index BETWEEN 0 AND 4), 
	FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE CASCADE
);
