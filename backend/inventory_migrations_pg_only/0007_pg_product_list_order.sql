-- 0007_pg_product_list_order.sql  (Postgres only)
--
-- Matches the ORDER BY of backend/services/product_service.query_products
-- (documented products first, on-sale before discontinued, then by
-- company/name), so an unfiltered page -- including deep pages -- reads the
-- index in order instead of sorting ~130k rows per request.

CREATE INDEX IF NOT EXISTS idx_products_list_order ON insurance_products (
    (CASE WHEN source = 'tii' THEN 1 ELSE 0 END),
    (CASE WHEN status = 'discontinued' THEN 1 ELSE 0 END),
    company_name,
    product_name
);
