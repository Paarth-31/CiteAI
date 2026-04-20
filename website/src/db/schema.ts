import { pgTable, serial, text, timestamp, integer, doublePrecision } from 'drizzle-orm/pg-core';

export const documents = pgTable('documents', {
  id: serial('id').primaryKey(), 
  title: text('title').notNull(),
  fileUrl: text('file_url'),
  fileSize: integer('file_size'),
  uploadDate: timestamp('upload_date', { mode: 'string' }),
  status: text('status').default('pending'),
  userId: integer('user_id'),
  createdAt: timestamp('created_at', { mode: 'string' }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { mode: 'string' }).defaultNow().notNull(),
});

export const citations = pgTable('citations', {
  id: serial('id').primaryKey(),
  documentId: integer('document_id')
    .references(() => documents.id, { onDelete: 'cascade' })
    .notNull(),
  title: text('title').notNull(),
  citations: integer('citations').default(0),
  year: integer('year'),
  x: doublePrecision('x').default(0),
  y: doublePrecision('y').default(0),
  createdAt: timestamp('created_at', { mode: 'string' }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { mode: 'string' }).defaultNow().notNull(),
});