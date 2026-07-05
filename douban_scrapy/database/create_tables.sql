-- 豆瓣电影 SQL Server 建表脚本（连接目标库后执行）

-- 电影表
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'Movies' AND xtype = 'U')
CREATE TABLE Movies (
    movie_id            VARCHAR(20)   NOT NULL PRIMARY KEY,
    name                NVARCHAR(500) NULL,
    poster_url          NVARCHAR(1000) NULL,
    plot                NVARCHAR(MAX) NULL,
    director            NVARCHAR(1000) NULL,
    screenwriter        NVARCHAR(1000) NULL,
    actors              NVARCHAR(MAX) NULL,
    genre               NVARCHAR(500) NULL,
    country             NVARCHAR(500) NULL,
    language            NVARCHAR(500) NULL,
    release_date        NVARCHAR(500) NULL,
    runtime             NVARCHAR(200) NULL,
    imdb_link           VARCHAR(200)  NULL,
    also_known_as       NVARCHAR(500) NULL,
    douban_rating       FLOAT         NULL,
    rating_count        INT           NULL DEFAULT 0,
    short_comment_count INT           NULL DEFAULT 0,
    crawl_time          DATETIME      NULL DEFAULT GETDATE(),
    is_crawled          BIT           NULL DEFAULT 1
);
GO

-- 短评表
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'ShortComments' AND xtype = 'U')
CREATE TABLE ShortComments (
    id             INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    movie_id       VARCHAR(20)       NOT NULL,
    nickname       NVARCHAR(200)     NULL,
    comment_time   NVARCHAR(100)     NULL,
    content        NVARCHAR(MAX)     NULL,
    helpful_votes  INT               NULL DEFAULT 0,
    crawl_time     DATETIME          NULL DEFAULT GETDATE(),
    CONSTRAINT FK_ShortComments_Movies FOREIGN KEY (movie_id) REFERENCES Movies(movie_id)
);
GO

IF NOT EXISTS (
    SELECT * FROM sys.indexes
    WHERE name = N'IX_ShortComments_MovieId'
      AND object_id = OBJECT_ID(N'dbo.ShortComments')
)
CREATE INDEX IX_ShortComments_MovieId ON ShortComments(movie_id);
GO
