-- The compliance graph lives in Postgres now (it used to be a separate Neo4j database).
-- A node is a label plus an id, with its properties as JSON. An edge joins two nodes with a type.
-- scripts/copy_graph_from_neo4j.py copies an existing Neo4j graph into these tables once.

create table if not exists graph_nodes (
  label text not null,
  id text not null,
  props jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (label, id)
);

-- Lookups by id alone, and the admin search over names
create index if not exists graph_nodes_id_idx on graph_nodes (id);
create index if not exists graph_nodes_name_idx on graph_nodes (label, lower(props->>'name'));

create table if not exists graph_edges (
  type text not null,
  src_label text not null,
  src_id text not null,
  dst_label text not null,
  dst_id text not null,
  props jsonb not null default '{}',
  created_at timestamptz not null default now(),
  primary key (type, src_label, src_id, dst_label, dst_id),
  foreign key (src_label, src_id) references graph_nodes (label, id) on delete cascade,
  foreign key (dst_label, dst_id) references graph_nodes (label, id) on delete cascade
);

create index if not exists graph_edges_dst_idx on graph_edges (dst_label, dst_id, type);
create index if not exists graph_edges_src_idx on graph_edges (src_label, src_id, type);
