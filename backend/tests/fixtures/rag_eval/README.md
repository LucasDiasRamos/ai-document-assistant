# RAG evaluation corpus

This directory contains a small synthetic, non-sensitive corpus used to measure retrieval quality independently from answer wording.

## Documents

- `employee_handbook.pdf`
  - page 1: remote-work allowance
  - page 2: training reimbursement
  - page 3: incident reporting
- `product_manual.pdf`
  - page 1: warranty period
  - page 2: battery charging/operation
  - page 3: preventive maintenance

The facts are intentionally synthetic and stable. They are not copied from a real company or customer.

## Cases

`cases.json` contains:

- answerable questions with expected document/page evidence;
- intentionally unsupported questions.

The evaluation uses deterministic test embeddings and does not call a paid generation provider. The pgvector integration portion runs when the configured PostgreSQL test database is available.
