-- Схема MS SQL для статистики прочтений author.today
-- Выполнить один раз: python scripts/init_mssql.py

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'books' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.books (
        id         INT NOT NULL, -- book_id из author.today (workId)
        title      NVARCHAR(300) NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_books_created_at DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_books PRIMARY KEY CLUSTERED (id)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'fetch_runs' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.fetch_runs (
        id           BIGINT IDENTITY(1, 1) NOT NULL,
        work_id      INT NOT NULL, -- FK -> books.id
        period_start DATE NOT NULL,
        period_end   DATE NOT NULL,
        fetched_at   DATETIME2(3) NOT NULL,
        value_type   NVARCHAR(16) NOT NULL
            CONSTRAINT DF_fetch_runs_value_type DEFAULT (N'hit'),
        CONSTRAINT PK_fetch_runs PRIMARY KEY CLUSTERED (id),
        CONSTRAINT CK_fetch_runs_value_type
            CHECK (value_type IN (N'hit', N'time', N'avgTime'))
    );

    ALTER TABLE dbo.fetch_runs
        ADD CONSTRAINT FK_fetch_runs_books
            FOREIGN KEY (work_id) REFERENCES dbo.books (id);

    CREATE INDEX IX_fetch_runs_work_id_fetched
        ON dbo.fetch_runs (work_id, fetched_at DESC);

    CREATE INDEX IX_fetch_runs_work_value_fetched
        ON dbo.fetch_runs (work_id, value_type, fetched_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'chapter_reads' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.chapter_reads (
        run_id       BIGINT NOT NULL,
        read_date    DATE NOT NULL,
        chapter_order INT NOT NULL, -- порядок главы на сайте (1..N)
        chapter_name NVARCHAR(500) NOT NULL,
        -- hit / time (сек) / avgTime: до ~1e10 с двумя знаками после запятой
        metric_value DECIMAL(12, 2) NULL,
        -- PK по порядку на сайте: одинаковые названия глав (интерлюдии и т.п.) допустимы
        CONSTRAINT PK_chapter_reads PRIMARY KEY CLUSTERED (run_id, read_date, chapter_order),
        CONSTRAINT FK_chapter_reads_fetch_runs
            FOREIGN KEY (run_id) REFERENCES dbo.fetch_runs (id) ON DELETE CASCADE
    );

    CREATE INDEX IX_chapter_reads_read_date
        ON dbo.chapter_reads (read_date, chapter_name);
END
GO

-- Миграция: chapter_order для уже существующей таблицы
IF COL_LENGTH('dbo.chapter_reads', 'chapter_order') IS NULL
BEGIN
    ALTER TABLE dbo.chapter_reads ADD chapter_order INT NULL;
END
GO

-- Миграция: PK (run_id, read_date, chapter_name) → (run_id, read_date, chapter_order)
-- Нужно для книг с двумя главами с одинаковым названием на сайте.
IF EXISTS (
    SELECT 1
    FROM sys.key_constraints kc
    INNER JOIN sys.index_columns ic
        ON kc.parent_object_id = ic.object_id
       AND kc.unique_index_id = ic.index_id
    INNER JOIN sys.columns c
        ON ic.object_id = c.object_id
       AND ic.column_id = c.column_id
    WHERE kc.parent_object_id = OBJECT_ID(N'dbo.chapter_reads')
      AND kc.name = N'PK_chapter_reads'
      AND c.name = N'chapter_name'
)
BEGIN
    ;WITH numbered AS (
        SELECT
            run_id,
            read_date,
            chapter_name,
            ROW_NUMBER() OVER (
                PARTITION BY run_id, read_date
                ORDER BY chapter_name
            ) AS rn
        FROM dbo.chapter_reads
        WHERE chapter_order IS NULL
    )
    UPDATE cr
    SET chapter_order = n.rn
    FROM dbo.chapter_reads AS cr
    INNER JOIN numbered AS n
        ON cr.run_id = n.run_id
       AND cr.read_date = n.read_date
       AND cr.chapter_name = n.chapter_name
    WHERE cr.chapter_order IS NULL;

    ALTER TABLE dbo.chapter_reads ALTER COLUMN chapter_order INT NOT NULL;

    ALTER TABLE dbo.chapter_reads DROP CONSTRAINT PK_chapter_reads;

    ALTER TABLE dbo.chapter_reads
        ADD CONSTRAINT PK_chapter_reads
            PRIMARY KEY CLUSTERED (run_id, read_date, chapter_order);
END
GO

-- Миграция: views → metric_value (существующие БД)
IF COL_LENGTH('dbo.chapter_reads', 'views') IS NOT NULL
   AND COL_LENGTH('dbo.chapter_reads', 'metric_value') IS NULL
BEGIN
    EXEC sp_rename N'dbo.chapter_reads.views', N'metric_value', N'COLUMN';
END
GO

-- Миграция: INT → DECIMAL(12,2) под time / avgTime
IF COL_LENGTH('dbo.chapter_reads', 'metric_value') IS NOT NULL
   AND EXISTS (
        SELECT 1
        FROM sys.columns AS c
        INNER JOIN sys.types AS t ON c.user_type_id = t.user_type_id
        WHERE c.object_id = OBJECT_ID(N'dbo.chapter_reads')
          AND c.name = N'metric_value'
          AND t.name IN (N'int', N'bigint', N'smallint', N'tinyint')
   )
BEGIN
    ALTER TABLE dbo.chapter_reads ALTER COLUMN metric_value DECIMAL(12, 2) NULL;
END
GO

-- Миграция: fetch_runs.value_type (hit / time / avgTime)
IF COL_LENGTH('dbo.fetch_runs', 'value_type') IS NULL
BEGIN
    ALTER TABLE dbo.fetch_runs ADD value_type NVARCHAR(16) NULL;
END
GO

IF COL_LENGTH('dbo.fetch_runs', 'value_type') IS NOT NULL
BEGIN
    UPDATE dbo.fetch_runs SET value_type = N'hit' WHERE value_type IS NULL;

    IF EXISTS (
        SELECT 1
        FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.fetch_runs')
          AND name = N'value_type'
          AND is_nullable = 1
    )
    BEGIN
        ALTER TABLE dbo.fetch_runs ALTER COLUMN value_type NVARCHAR(16) NOT NULL;
    END

    IF NOT EXISTS (
        SELECT 1 FROM sys.default_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.fetch_runs')
          AND name = N'DF_fetch_runs_value_type'
    )
    BEGIN
        ALTER TABLE dbo.fetch_runs
            ADD CONSTRAINT DF_fetch_runs_value_type DEFAULT (N'hit') FOR value_type;
    END

    IF NOT EXISTS (
        SELECT 1 FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.fetch_runs')
          AND name = N'CK_fetch_runs_value_type'
    )
    BEGIN
        ALTER TABLE dbo.fetch_runs
            ADD CONSTRAINT CK_fetch_runs_value_type
                CHECK (value_type IN (N'hit', N'time', N'avgTime'));
    END

    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.fetch_runs')
          AND name = N'IX_fetch_runs_work_value_fetched'
    )
    BEGIN
        CREATE INDEX IX_fetch_runs_work_value_fetched
            ON dbo.fetch_runs (work_id, value_type, fetched_at DESC);
    END
END
GO

-- Заметки к книге (дата + текст; подсветка на тренде)
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'book_notes' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.book_notes (
        id         BIGINT IDENTITY(1, 1) NOT NULL,
        book_id    INT NOT NULL,
        note_date  DATE NOT NULL,
        body       NVARCHAR(1000) NOT NULL,
        created_at DATETIME2(3) NOT NULL
            CONSTRAINT DF_book_notes_created_at DEFAULT (SYSUTCDATETIME()),
        updated_at DATETIME2(3) NULL,
        CONSTRAINT PK_book_notes PRIMARY KEY CLUSTERED (id),
        CONSTRAINT FK_book_notes_books
            FOREIGN KEY (book_id) REFERENCES dbo.books (id) ON DELETE CASCADE
    );

    CREATE INDEX IX_book_notes_book_date
        ON dbo.book_notes (book_id, note_date);
END
GO
