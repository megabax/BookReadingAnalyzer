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
        CONSTRAINT PK_fetch_runs PRIMARY KEY CLUSTERED (id)
    );

    ALTER TABLE dbo.fetch_runs
        ADD CONSTRAINT FK_fetch_runs_books
            FOREIGN KEY (work_id) REFERENCES dbo.books (id);

    CREATE INDEX IX_fetch_runs_work_id_fetched
        ON dbo.fetch_runs (work_id, fetched_at DESC);
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
        CONSTRAINT PK_chapter_reads PRIMARY KEY CLUSTERED (run_id, read_date, chapter_name),
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
