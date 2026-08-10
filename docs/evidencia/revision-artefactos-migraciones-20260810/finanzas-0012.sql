BEGIN;
ALTER TABLE "finanzas_lotepago"
    ADD COLUMN "respaldo" varchar(100) NULL;
ALTER TABLE "finanzas_payment"
    ADD COLUMN "clave_idempotencia" varchar(160) NULL UNIQUE;
ALTER TABLE "finanzas_payment"
    ADD COLUMN "disciplina_id" bigint NULL
    CONSTRAINT "finanzas_payment_disciplina_id_d3d40743_fk_academia_"
    REFERENCES "academia_disciplina" ("id") DEFERRABLE INITIALLY DEFERRED;
SET CONSTRAINTS "finanzas_payment_disciplina_id_d3d40743_fk_academia_" IMMEDIATE;
ALTER TABLE "finanzas_payment"
    ADD COLUMN "registrado_por_id" integer NULL
    CONSTRAINT "finanzas_payment_registrado_por_id_14e1aeb7_fk_auth_user_id"
    REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
SET CONSTRAINTS "finanzas_payment_registrado_por_id_14e1aeb7_fk_auth_user_id" IMMEDIATE;
ALTER TABLE "finanzas_payment"
    ADD COLUMN "respaldo" varchar(100) NULL;
ALTER TABLE "finanzas_payment"
    ADD COLUMN "transaccion_id" bigint NULL UNIQUE
    CONSTRAINT "finanzas_payment_transaccion_id_7a5b8c20_fk_finanzas_"
    REFERENCES "finanzas_transaction" ("id") DEFERRABLE INITIALLY DEFERRED;
SET CONSTRAINTS "finanzas_payment_transaccion_id_7a5b8c20_fk_finanzas_" IMMEDIATE;
ALTER TABLE "finanzas_transaction"
    ADD COLUMN "creado_por_id" integer NULL
    CONSTRAINT "finanzas_transaction_creado_por_id_8ef7a634_fk_auth_user_id"
    REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
SET CONSTRAINTS "finanzas_transaction_creado_por_id_8ef7a634_fk_auth_user_id" IMMEDIATE;

CREATE INDEX "finanzas_payment_clave_idempotencia_eb77c6c8_like"
    ON "finanzas_payment" ("clave_idempotencia" varchar_pattern_ops);
CREATE INDEX "finanzas_payment_disciplina_id_d3d40743"
    ON "finanzas_payment" ("disciplina_id");
CREATE INDEX "finanzas_payment_registrado_por_id_14e1aeb7"
    ON "finanzas_payment" ("registrado_por_id");
CREATE INDEX "finanzas_transaction_creado_por_id_8ef7a634"
    ON "finanzas_transaction" ("creado_por_id");
COMMIT;
