import { Prisma } from "@prisma/client";

export interface ExactPrincipalCatalogRow {
  serverVersionNumber: number;
  sessionRole: string;
  sessionSearchPath: string;
  loginRole: string;
  loginCanLogin: boolean;
  loginSuperuser: boolean;
  loginCreateDb: boolean;
  loginCreateRole: boolean;
  loginInherits: boolean;
  loginReplication: boolean;
  loginBypassRls: boolean;
  loginConnectionLimit: number;
  loginValidUntil: Date | null;
  loginHasExactVerifier: boolean;
  loginMemberships: string[];
  loginHasAdminMembership: boolean;
  loginHasNonInheritedMembership: boolean;
  loginHasSetMembership: boolean;
  loginHasNonSuperuserGrantor: boolean;
  loginMembers: string[];
  loginHasDirectAuthority: boolean;
  boundaryRole: string;
  boundaryCanLogin: boolean;
  boundarySuperuser: boolean;
  boundaryCreateDb: boolean;
  boundaryCreateRole: boolean;
  boundaryInherits: boolean;
  boundaryReplication: boolean;
  boundaryBypassRls: boolean;
  boundaryConnectionLimit: number;
  boundaryValidUntil: Date | null;
  boundaryMembers: string[];
  boundaryHasAdminMember: boolean;
  boundaryHasNonInheritedMember: boolean;
  boundaryHasSetMember: boolean;
  boundaryHasNonSuperuserGrantor: boolean;
  boundaryMemberships: string[];
  readAllDataClosureIsExact: boolean;
  boundaryHasPassword: boolean;
  boundaryAclCount: number;
  boundaryAclSha256: string;
  boundaryAclManifest: string[];
  applicationAclCount: number;
  applicationAclSha256: string;
  applicationAclManifest: string[];
  applicationPublicAclCount: number;
  applicationPublicAclSha256: string;
  applicationPublicAclManifest: string[];
  systemPublicAclCount: number;
  systemPublicAclSha256: string;
  systemPublicAclManifest: string[];
  futureDefaultAclCount: number;
  futureDefaultAclSha256: string;
  futureDefaultAclManifest: string[];
  boundaryHasUnexpectedDependency: boolean;
  graphHasForbiddenGrantor: boolean;
  databaseHasGlobalRoleSettings: boolean;
  hasApplicablePolicy: boolean;
  hasPublicUserMapping: boolean;
  hasBoundaryUserMapping: boolean;
  hasForeignDataAuthority: boolean;
  hasWritableApplicationSchema: boolean;
  hasUnapprovedApplicationAuthority: boolean;
  hasUnsafeExecutableCapability: boolean;
  hasForbiddenLargeObjectFunctionAuthority: boolean;
  hasLargeObjects: boolean;
  loginCanConnectCurrentDatabase: boolean;
  boundaryCanConnectCurrentDatabase: boolean;
  hasForbiddenDatabaseAuthority: boolean;
}

/**
 * Runtime-readable PostgreSQL 16 catalog proof. All manifest entries are JSON
 * arrays, ordered with the C collation, and duplicates are deliberately kept.
 * The caller's exact pg_catalog,public startup search_path is part of the
 * contract. Capturing it without mutating a GUC keeps PostgreSQL deparsers
 * deterministic across prepared, literal, runtime, and migration execution.
 */
export function exactDatabasePrincipalCatalogQuery(input: {
  loginRole: string;
  boundaryRole: string;
  includeManifestEntries?: boolean;
  requireSessionRole?: boolean;
}): Prisma.Sql {
  return Prisma.sql`
    WITH original_environment AS MATERIALIZED (
      SELECT pg_catalog.current_setting('search_path') AS original_search_path
    ),
    normalized_environment AS MATERIALIZED (
      SELECT original_environment.original_search_path,
        original_environment.original_search_path AS path
      FROM original_environment
    ),
    selected AS MATERIALIZED (
      SELECT login.oid AS login_oid,
        boundary.oid AS boundary_oid,
        database.oid AS database_oid,
        database.datdba AS database_owner_oid,
        normalized_environment.original_search_path
      FROM pg_catalog.pg_roles login
      CROSS JOIN pg_catalog.pg_roles boundary
      JOIN pg_catalog.pg_database database
        ON database.datname = pg_catalog.current_database()
      CROSS JOIN normalized_environment
      WHERE login.rolname = ${input.loginRole}
        AND boundary.rolname = ${input.boundaryRole}
    ),
    relation_catalog AS MATERIALIZED (
      SELECT object.oid,
        object.relacl,
        object.relowner,
        object.relkind,
        namespace.nspname,
        object.relname,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE
              WHEN object.relowner = selected.boundary_oid THEN '<boundary>'
              WHEN object.relowner = selected.database_owner_oid
                THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>')
            END,
            object.relkind,
            object.relpersistence,
            object.relrowsecurity,
            object.relforcerowsecurity,
            object.relreplident,
            object.relhasrules,
            object.relispartition,
            CASE WHEN object.relam = 0 THEN NULL
              ELSE pg_catalog.jsonb_build_array(
                access_method.amname, access_method.amtype
              ) END,
            CASE WHEN object.reltablespace = 0
              THEN pg_catalog.jsonb_build_array(
                '<database-default>', database_tablespace.spcname
              )
              ELSE pg_catalog.jsonb_build_array(
                '<relation>', relation_tablespace.spcname
              ) END,
            pg_catalog.pg_get_expr(
              object.relpartbound, object.oid, FALSE
            ),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(option ORDER BY option COLLATE "C")
              FROM pg_catalog.unnest(object.reloptions) option
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  attribute.attnum,
                  attribute.attname,
                  pg_catalog.format_type(
                    attribute.atttypid, attribute.atttypmod
                  ),
                  attribute.attnotnull,
                  attribute.attidentity,
                  attribute.attgenerated,
                  pg_catalog.pg_get_expr(
                    default_value.adbin, default_value.adrelid, FALSE
                  )
                ) ORDER BY attribute.attnum
              )
              FROM pg_catalog.pg_attribute attribute
              LEFT JOIN pg_catalog.pg_attrdef default_value
                ON default_value.adrelid = attribute.attrelid
               AND default_value.adnum = attribute.attnum
              WHERE attribute.attrelid = object.oid
                AND attribute.attnum > 0
                AND attribute.attisdropped = FALSE
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  trigger.tgname,
                  trigger.tgenabled,
                  trigger.tgisinternal,
                  pg_catalog.pg_get_triggerdef(trigger.oid, FALSE),
                  CASE
                    WHEN trigger_function.proowner =
                        selected.database_owner_oid
                      THEN '<current-db-owner>'
                    ELSE COALESCE(trigger_owner.rolname, '<unknown-owner>')
                  END,
                  pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
                    pg_catalog.pg_get_functiondef(trigger_function.oid),
                    'UTF8'
                  )), 'hex')
                ) ORDER BY trigger.tgname COLLATE "C"
              )
              FROM pg_catalog.pg_trigger trigger
              JOIN pg_catalog.pg_proc trigger_function
                ON trigger_function.oid = trigger.tgfoid
              LEFT JOIN pg_catalog.pg_roles trigger_owner
                ON trigger_owner.oid = trigger_function.proowner
              WHERE trigger.tgrelid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  rule.rulename,
                  rule.ev_type,
                  rule.ev_enabled,
                  rule.is_instead,
                  pg_catalog.pg_get_ruledef(rule.oid, FALSE)
                ) ORDER BY rule.rulename COLLATE "C"
              )
              FROM pg_catalog.pg_rewrite rule
              WHERE rule.ev_class = object.oid
                AND NOT (
                  object.relkind IN ('v', 'm')
                  AND rule.rulename = '_RETURN'
                )
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  constraint_object.conname,
                  constraint_object.contype,
                  constraint_object.condeferrable,
                  constraint_object.condeferred,
                  constraint_object.convalidated,
                  constraint_object.conislocal,
                  constraint_object.coninhcount,
                  constraint_object.connoinherit,
                  referenced_namespace.nspname,
                  referenced_relation.relname,
                  constraint_index.relname,
                  pg_catalog.pg_get_constraintdef(
                    constraint_object.oid, FALSE
                  )
                ) ORDER BY constraint_object.conname COLLATE "C",
                  constraint_object.contype
              )
              FROM pg_catalog.pg_constraint constraint_object
              LEFT JOIN pg_catalog.pg_class referenced_relation
                ON referenced_relation.oid = constraint_object.confrelid
              LEFT JOIN pg_catalog.pg_namespace referenced_namespace
                ON referenced_namespace.oid =
                    referenced_relation.relnamespace
              LEFT JOIN pg_catalog.pg_class constraint_index
                ON constraint_index.oid = constraint_object.conindid
              WHERE constraint_object.conrelid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  index_namespace.nspname,
                  index_relation.relname,
                  index_catalog.indisunique,
                  index_catalog.indisprimary,
                  index_catalog.indisexclusion,
                  index_catalog.indnullsnotdistinct,
                  index_catalog.indimmediate,
                  index_catalog.indisclustered,
                  index_catalog.indisvalid,
                  index_catalog.indcheckxmin,
                  index_catalog.indisready,
                  index_catalog.indislive,
                  index_catalog.indisreplident,
                  index_catalog.indnatts,
                  index_catalog.indnkeyatts,
                  pg_catalog.pg_get_indexdef(
                    index_catalog.indexrelid, 0, FALSE
                  ),
                  pg_catalog.pg_get_expr(
                    index_catalog.indexprs,
                    index_catalog.indrelid,
                    FALSE
                  ),
                  pg_catalog.pg_get_expr(
                    index_catalog.indpred,
                    index_catalog.indrelid,
                    FALSE
                  )
                ) ORDER BY index_namespace.nspname COLLATE "C",
                  index_relation.relname COLLATE "C"
              )
              FROM pg_catalog.pg_index index_catalog
              JOIN pg_catalog.pg_class index_relation
                ON index_relation.oid = index_catalog.indexrelid
              JOIN pg_catalog.pg_namespace index_namespace
                ON index_namespace.oid = index_relation.relnamespace
              WHERE index_catalog.indrelid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  parent_namespace.nspname,
                  parent_relation.relname,
                  inheritance.inhseqno,
                  inheritance.inhdetachpending
                ) ORDER BY inheritance.inhseqno,
                  parent_namespace.nspname COLLATE "C",
                  parent_relation.relname COLLATE "C"
              )
              FROM pg_catalog.pg_inherits inheritance
              JOIN pg_catalog.pg_class parent_relation
                ON parent_relation.oid = inheritance.inhparent
              JOIN pg_catalog.pg_namespace parent_namespace
                ON parent_namespace.oid = parent_relation.relnamespace
              WHERE inheritance.inhrelid = object.oid
            ), '[]'::pg_catalog.jsonb),
            (
              SELECT pg_catalog.jsonb_build_array(
                partitioned.partstrat,
                partitioned.partnatts,
                partitioned.partdefid <> 0,
                pg_catalog.pg_get_partkeydef(partitioned.partrelid)
              )
              FROM pg_catalog.pg_partitioned_table partitioned
              WHERE partitioned.partrelid = object.oid
            ),
            (
              SELECT pg_catalog.jsonb_build_array(
                pg_catalog.format_type(sequence_object.seqtypid, NULL),
                sequence_object.seqstart::TEXT,
                sequence_object.seqincrement::TEXT,
                sequence_object.seqmax::TEXT,
                sequence_object.seqmin::TEXT,
                sequence_object.seqcache::TEXT,
                sequence_object.seqcycle
              )
              FROM pg_catalog.pg_sequence sequence_object
              WHERE sequence_object.seqrelid = object.oid
            ),
            (
              SELECT pg_catalog.jsonb_build_array(
                foreign_server.srvname,
                CASE
                  WHEN foreign_server.srvowner = selected.database_owner_oid
                    THEN '<current-db-owner>'
                  ELSE COALESCE(server_owner.rolname, '<unknown-owner>')
                END,
                foreign_server.srvtype,
                foreign_server.srvversion,
                COALESCE((
                  SELECT pg_catalog.jsonb_agg(
                    option ORDER BY option COLLATE "C"
                  )
                  FROM pg_catalog.unnest(foreign_server.srvoptions) option
                ), '[]'::pg_catalog.jsonb),
                foreign_wrapper.fdwname,
                CASE
                  WHEN foreign_wrapper.fdwowner = selected.database_owner_oid
                    THEN '<current-db-owner>'
                  ELSE COALESCE(wrapper_owner.rolname, '<unknown-owner>')
                END,
                COALESCE((
                  SELECT pg_catalog.jsonb_agg(
                    option ORDER BY option COLLATE "C"
                  )
                  FROM pg_catalog.unnest(foreign_wrapper.fdwoptions) option
                ), '[]'::pg_catalog.jsonb),
                handler_namespace.nspname,
                handler_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  handler_function.oid
                ),
                validator_namespace.nspname,
                validator_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  validator_function.oid
                ),
                COALESCE((
                  SELECT pg_catalog.jsonb_agg(
                    option ORDER BY option COLLATE "C"
                  )
                  FROM pg_catalog.unnest(foreign_table.ftoptions) option
                ), '[]'::pg_catalog.jsonb)
              )
              FROM pg_catalog.pg_foreign_table foreign_table
              JOIN pg_catalog.pg_foreign_server foreign_server
                ON foreign_server.oid = foreign_table.ftserver
              JOIN pg_catalog.pg_foreign_data_wrapper foreign_wrapper
                ON foreign_wrapper.oid = foreign_server.srvfdw
              LEFT JOIN pg_catalog.pg_roles server_owner
                ON server_owner.oid = foreign_server.srvowner
              LEFT JOIN pg_catalog.pg_roles wrapper_owner
                ON wrapper_owner.oid = foreign_wrapper.fdwowner
              LEFT JOIN pg_catalog.pg_proc handler_function
                ON handler_function.oid = foreign_wrapper.fdwhandler
              LEFT JOIN pg_catalog.pg_namespace handler_namespace
                ON handler_namespace.oid = handler_function.pronamespace
              LEFT JOIN pg_catalog.pg_proc validator_function
                ON validator_function.oid = foreign_wrapper.fdwvalidator
              LEFT JOIN pg_catalog.pg_namespace validator_namespace
                ON validator_namespace.oid = validator_function.pronamespace
              WHERE foreign_table.ftrelid = object.oid
            ),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  policy.polname,
                  policy.polcmd,
                  policy.polpermissive,
                  ARRAY(
                    SELECT CASE WHEN policy_role.role_oid = 0
                      THEN '<public>'
                      ELSE COALESCE(role.rolname,
                        pg_catalog.format(
                          '<oid:%s>', policy_role.role_oid
                        )) END
                    FROM pg_catalog.unnest(policy.polroles)
                      WITH ORDINALITY policy_role(role_oid, ordinal)
                    LEFT JOIN pg_catalog.pg_roles role
                      ON role.oid = policy_role.role_oid
                    ORDER BY policy_role.ordinal
                  ),
                  pg_catalog.pg_get_expr(
                    policy.polqual, policy.polrelid, FALSE
                  ),
                  pg_catalog.pg_get_expr(
                    policy.polwithcheck, policy.polrelid, FALSE
                  )
                ) ORDER BY policy.polname COLLATE "C"
              )
              FROM pg_catalog.pg_policy policy
              WHERE policy.polrelid = object.oid
            ), '[]'::pg_catalog.jsonb),
            extension.extname,
            extension.extversion,
            CASE WHEN object.relkind IN ('v', 'm')
              THEN pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
                pg_catalog.pg_get_viewdef(object.oid, FALSE), 'UTF8'
              )), 'hex')
              ELSE NULL
            END
          )::text,
          'UTF8'
        )), 'hex') AS semantic_sha256
      FROM pg_catalog.pg_class object
      JOIN pg_catalog.pg_namespace namespace
        ON namespace.oid = object.relnamespace
      JOIN selected ON TRUE
      CROSS JOIN normalized_environment
      LEFT JOIN pg_catalog.pg_am access_method
        ON access_method.oid = object.relam
      LEFT JOIN pg_catalog.pg_tablespace relation_tablespace
        ON relation_tablespace.oid = object.reltablespace
      LEFT JOIN pg_catalog.pg_database current_database_object
        ON current_database_object.oid = selected.database_oid
      LEFT JOIN pg_catalog.pg_tablespace database_tablespace
        ON database_tablespace.oid = current_database_object.dattablespace
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.relowner
      LEFT JOIN pg_catalog.pg_depend extension_dependency
        ON extension_dependency.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
       AND extension_dependency.objid = object.oid
       AND extension_dependency.objsubid = 0
       AND extension_dependency.refclassid =
           'pg_catalog.pg_extension'::pg_catalog.regclass
       AND extension_dependency.deptype = 'e'
      LEFT JOIN pg_catalog.pg_extension extension
        ON extension.oid = extension_dependency.refobjid
      WHERE (
        namespace.nspname !~ '^pg_temp_[0-9]+$'
        AND namespace.nspname !~ '^pg_toast_temp_[0-9]+$'
      ) OR EXISTS (
        SELECT 1
        FROM pg_catalog.aclexplode(object.relacl) privilege
        WHERE privilege.grantee = selected.boundary_oid
           OR privilege.grantor = selected.boundary_oid
      ) OR EXISTS (
        SELECT 1
        FROM pg_catalog.pg_attribute attribute
        CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) privilege
        WHERE attribute.attrelid = object.oid
          AND (privilege.grantee = selected.boundary_oid
            OR privilege.grantor = selected.boundary_oid)
      )
    ),
    callable_catalog AS MATERIALIZED (
      SELECT object.oid,
        object.proacl,
        object.proowner,
        object.prokind,
        object.prosecdef,
        object.proconfig,
        namespace.nspname,
        object.proname,
        pg_catalog.pg_get_function_identity_arguments(object.oid)
          AS identity_arguments,
        extension.extname,
        extension.extversion,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE
              WHEN object.proowner = selected.boundary_oid THEN '<boundary>'
              WHEN object.proowner = selected.database_owner_oid
                THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>')
            END,
            language.lanname,
            object.prokind,
            object.prosecdef,
            object.proleakproof,
            object.proisstrict,
            object.proretset,
            object.provolatile,
            object.proparallel,
            COALESCE((
              SELECT pg_catalog.jsonb_agg(setting ORDER BY setting COLLATE "C")
              FROM pg_catalog.unnest(object.proconfig) setting
            ), '[]'::pg_catalog.jsonb),
            extension.extname,
            extension.extversion,
            CASE WHEN object.prokind IN ('a', 'w') THEN NULL
              ELSE pg_catalog.pg_get_functiondef(object.oid)
            END
          )::text,
          'UTF8'
        )), 'hex') AS semantic_sha256
      FROM pg_catalog.pg_proc object
      JOIN pg_catalog.pg_namespace namespace
        ON namespace.oid = object.pronamespace
      JOIN pg_catalog.pg_language language ON language.oid = object.prolang
      JOIN selected ON TRUE
      CROSS JOIN normalized_environment
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.proowner
      LEFT JOIN pg_catalog.pg_depend extension_dependency
        ON extension_dependency.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
       AND extension_dependency.objid = object.oid
       AND extension_dependency.objsubid = 0
       AND extension_dependency.refclassid =
           'pg_catalog.pg_extension'::pg_catalog.regclass
       AND extension_dependency.deptype = 'e'
      LEFT JOIN pg_catalog.pg_extension extension
        ON extension.oid = extension_dependency.refobjid
      WHERE (
        namespace.nspname !~ '^pg_temp_[0-9]+$'
        AND namespace.nspname !~ '^pg_toast_temp_[0-9]+$'
      ) OR EXISTS (
        SELECT 1
        FROM pg_catalog.aclexplode(object.proacl) privilege
        WHERE privilege.grantee = selected.boundary_oid
           OR privilege.grantor = selected.boundary_oid
      )
    ),
    application_type_catalog AS MATERIALIZED (
      SELECT object.oid,
        object.typacl,
        object.typowner,
        namespace.nspname,
        object.typname,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE WHEN object.typowner = selected.database_owner_oid
              THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
            object.typtype,
            object.typcategory,
            object.typispreferred,
            object.typnotnull,
            object.typlen,
            object.typbyval,
            object.typalign,
            object.typstorage,
            object.typndims,
            CASE WHEN object.typbasetype = 0 THEN NULL
              ELSE pg_catalog.format_type(
                object.typbasetype, object.typtypmod
              ) END,
            CASE WHEN object.typelem = 0 THEN NULL
              ELSE pg_catalog.format_type(object.typelem, NULL) END,
            object.typdefault,
            pg_catalog.pg_get_expr(object.typdefaultbin, 0, FALSE),
            (
              SELECT pg_catalog.jsonb_build_array(
                collation_namespace.nspname, collation_object.collname
              )
              FROM pg_catalog.pg_collation collation_object
              JOIN pg_catalog.pg_namespace collation_namespace
                ON collation_namespace.oid = collation_object.collnamespace
              WHERE collation_object.oid = object.typcollation
            ),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  enum_value.enumlabel,
                  enum_value.enumsortorder::TEXT
                ) ORDER BY enum_value.enumsortorder, enum_value.oid
              )
              FROM pg_catalog.pg_enum enum_value
              WHERE enum_value.enumtypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  domain_constraint.conname,
                  domain_constraint.condeferrable,
                  domain_constraint.condeferred,
                  domain_constraint.convalidated,
                  pg_catalog.pg_get_constraintdef(
                    domain_constraint.oid, FALSE
                  )
                ) ORDER BY domain_constraint.conname COLLATE "C"
              )
              FROM pg_catalog.pg_constraint domain_constraint
              WHERE domain_constraint.contypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            (
              SELECT pg_catalog.jsonb_build_array(
                pg_catalog.format_type(range_type.rngsubtype, NULL),
                pg_catalog.format_type(range_type.rngmultitypid, NULL),
                range_collation_namespace.nspname,
                range_collation.collname,
                range_opclass_namespace.nspname,
                range_opclass.opcname,
                canonical_namespace.nspname,
                canonical_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  canonical_function.oid
                ),
                subdiff_namespace.nspname,
                subdiff_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  subdiff_function.oid
                )
              )
              FROM pg_catalog.pg_range range_type
              JOIN pg_catalog.pg_opclass range_opclass
                ON range_opclass.oid = range_type.rngsubopc
              JOIN pg_catalog.pg_namespace range_opclass_namespace
                ON range_opclass_namespace.oid = range_opclass.opcnamespace
              LEFT JOIN pg_catalog.pg_collation range_collation
                ON range_collation.oid = range_type.rngcollation
              LEFT JOIN pg_catalog.pg_namespace range_collation_namespace
                ON range_collation_namespace.oid =
                    range_collation.collnamespace
              LEFT JOIN pg_catalog.pg_proc canonical_function
                ON canonical_function.oid = range_type.rngcanonical
              LEFT JOIN pg_catalog.pg_namespace canonical_namespace
                ON canonical_namespace.oid =
                    canonical_function.pronamespace
              LEFT JOIN pg_catalog.pg_proc subdiff_function
                ON subdiff_function.oid = range_type.rngsubdiff
              LEFT JOIN pg_catalog.pg_namespace subdiff_namespace
                ON subdiff_namespace.oid = subdiff_function.pronamespace
              WHERE range_type.rngtypid = object.oid
            ),
            extension.extname,
            extension.extversion
          )::text, 'UTF8'
        )), 'hex') AS semantic_sha256
      FROM pg_catalog.pg_type object
      JOIN pg_catalog.pg_namespace namespace
        ON namespace.oid = object.typnamespace
      JOIN selected ON TRUE
      CROSS JOIN normalized_environment
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.typowner
      LEFT JOIN pg_catalog.pg_depend extension_dependency
        ON extension_dependency.classid =
            'pg_catalog.pg_type'::pg_catalog.regclass
       AND extension_dependency.objid = object.oid
       AND extension_dependency.objsubid = 0
       AND extension_dependency.refclassid =
           'pg_catalog.pg_extension'::pg_catalog.regclass
       AND extension_dependency.deptype = 'e'
      LEFT JOIN pg_catalog.pg_extension extension
        ON extension.oid = extension_dependency.refobjid
      WHERE namespace.nspname !~ '^pg_'
        AND namespace.nspname <> 'information_schema'
    ),
    boundary_manifest AS MATERIALIZED (
      SELECT pg_catalog.jsonb_build_array(
        'relation',
        pg_catalog.jsonb_build_array(
          object.nspname, object.relname, object.relkind
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantee = object.relowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantor = object.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        object.semantic_sha256
      )::text AS entry
      FROM relation_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(object.relacl) privilege
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE privilege.grantee = selected.boundary_oid
         OR privilege.grantor = selected.boundary_oid

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'column',
        pg_catalog.jsonb_build_array(
          relation.nspname, relation.relname, attribute.attnum,
          attribute.attname
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantee = relation.relowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantor = relation.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        relation.semantic_sha256
      )::text
      FROM pg_catalog.pg_attribute attribute
      JOIN relation_catalog relation ON relation.oid = attribute.attrelid
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) privilege
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE privilege.grantee = selected.boundary_oid
         OR privilege.grantor = selected.boundary_oid

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'schema', object.nspname,
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantee = object.nspowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantor = object.nspowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE
              WHEN object.nspowner = selected.boundary_oid THEN '<boundary>'
              WHEN object.nspowner = selected.database_owner_oid
                THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>')
            END
          )::text, 'UTF8'
        )), 'hex')
      )::text
      FROM pg_catalog.pg_namespace object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(object.nspacl) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.nspowner
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE privilege.grantee = selected.boundary_oid
         OR privilege.grantor = selected.boundary_oid

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'function',
        pg_catalog.jsonb_build_array(
          object.nspname, object.proname, object.identity_arguments,
          object.prokind
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantee = object.proowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantor = object.proowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        object.semantic_sha256
      )::text
      FROM callable_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(object.proacl) privilege
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE privilege.grantee = selected.boundary_oid
         OR privilege.grantor = selected.boundary_oid

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'type',
        pg_catalog.jsonb_build_array(namespace.nspname, object.typname),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantee = object.typowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = selected.boundary_oid THEN '<boundary>'
          WHEN privilege.grantor = object.typowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE
              WHEN object.typowner = selected.boundary_oid THEN '<boundary>'
              WHEN object.typowner = selected.database_owner_oid
                THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>')
            END,
            object.typtype, object.typcategory, object.typispreferred,
            object.typnotnull,
            object.typlen,
            object.typbyval,
            object.typalign,
            object.typstorage,
            object.typndims,
            CASE WHEN object.typbasetype = 0 THEN NULL
              ELSE pg_catalog.format_type(
                object.typbasetype, object.typtypmod
              ) END,
            CASE WHEN object.typelem = 0 THEN NULL
              ELSE pg_catalog.format_type(object.typelem, NULL) END,
            object.typdefault,
            pg_catalog.pg_get_expr(object.typdefaultbin, 0, FALSE),
            (
              SELECT pg_catalog.jsonb_build_array(
                collation_namespace.nspname, collation_object.collname
              )
              FROM pg_catalog.pg_collation collation_object
              JOIN pg_catalog.pg_namespace collation_namespace
                ON collation_namespace.oid = collation_object.collnamespace
              WHERE collation_object.oid = object.typcollation
            ),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  enum_value.enumlabel,
                  enum_value.enumsortorder::TEXT
                ) ORDER BY enum_value.enumsortorder, enum_value.oid
              )
              FROM pg_catalog.pg_enum enum_value
              WHERE enum_value.enumtypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  domain_constraint.conname,
                  domain_constraint.condeferrable,
                  domain_constraint.condeferred,
                  domain_constraint.convalidated,
                  pg_catalog.pg_get_constraintdef(
                    domain_constraint.oid, FALSE
                  )
                ) ORDER BY domain_constraint.conname COLLATE "C"
              )
              FROM pg_catalog.pg_constraint domain_constraint
              WHERE domain_constraint.contypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            (
              SELECT pg_catalog.jsonb_build_array(
                pg_catalog.format_type(range_type.rngsubtype, NULL),
                pg_catalog.format_type(range_type.rngmultitypid, NULL),
                range_collation_namespace.nspname,
                range_collation.collname,
                range_opclass_namespace.nspname,
                range_opclass.opcname,
                canonical_namespace.nspname,
                canonical_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  canonical_function.oid
                ),
                subdiff_namespace.nspname,
                subdiff_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  subdiff_function.oid
                )
              )
              FROM pg_catalog.pg_range range_type
              JOIN pg_catalog.pg_opclass range_opclass
                ON range_opclass.oid = range_type.rngsubopc
              JOIN pg_catalog.pg_namespace range_opclass_namespace
                ON range_opclass_namespace.oid = range_opclass.opcnamespace
              LEFT JOIN pg_catalog.pg_collation range_collation
                ON range_collation.oid = range_type.rngcollation
              LEFT JOIN pg_catalog.pg_namespace range_collation_namespace
                ON range_collation_namespace.oid =
                    range_collation.collnamespace
              LEFT JOIN pg_catalog.pg_proc canonical_function
                ON canonical_function.oid = range_type.rngcanonical
              LEFT JOIN pg_catalog.pg_namespace canonical_namespace
                ON canonical_namespace.oid =
                    canonical_function.pronamespace
              LEFT JOIN pg_catalog.pg_proc subdiff_function
                ON subdiff_function.oid = range_type.rngsubdiff
              LEFT JOIN pg_catalog.pg_namespace subdiff_namespace
                ON subdiff_namespace.oid = subdiff_function.pronamespace
              WHERE range_type.rngtypid = object.oid
            ),
            extension.extname, extension.extversion
          )::text, 'UTF8'
        )), 'hex')
      )::text
      FROM pg_catalog.pg_type object
      JOIN pg_catalog.pg_namespace namespace ON namespace.oid = object.typnamespace
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(object.typacl) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.typowner
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      LEFT JOIN pg_catalog.pg_depend extension_dependency
        ON extension_dependency.classid = 'pg_catalog.pg_type'::pg_catalog.regclass
       AND extension_dependency.objid = object.oid
       AND extension_dependency.objsubid = 0
       AND extension_dependency.refclassid =
           'pg_catalog.pg_extension'::pg_catalog.regclass
       AND extension_dependency.deptype = 'e'
      LEFT JOIN pg_catalog.pg_extension extension
        ON extension.oid = extension_dependency.refobjid
      WHERE privilege.grantee = selected.boundary_oid
         OR privilege.grantor = selected.boundary_oid

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        class_name, identity,
        CASE
          WHEN acl.grantee = 0 THEN '<public>'
          WHEN acl.grantee = selected.boundary_oid THEN '<boundary>'
          WHEN acl.grantee = owner_oid THEN '<object-owner>'
          WHEN acl.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', acl.grantee))
        END,
        CASE
          WHEN acl.grantor = selected.boundary_oid THEN '<boundary>'
          WHEN acl.grantor = owner_oid THEN '<object-owner>'
          WHEN acl.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', acl.grantor))
        END,
        acl.privilege_type, acl.is_grantable, semantic_sha256
      )::text
      FROM selected
      CROSS JOIN LATERAL (
        SELECT 'database'::text AS class_name,
          CASE WHEN object.oid = selected.database_oid
            THEN '<current>' ELSE object.datname END AS identity,
          object.datdba AS owner_oid, object.datacl AS acl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.datdba = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              object.datallowconn, object.datconnlimit
            )::text, 'UTF8'
          )), 'hex') AS semantic_sha256
        FROM pg_catalog.pg_database object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.datdba
        UNION ALL
        SELECT 'language', object.lanname, object.lanowner, object.lanacl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.lanowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              object.lanpltrusted
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_language object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.lanowner
        UNION ALL
        SELECT 'foreign_data_wrapper', object.fdwname, object.fdwowner,
          object.fdwacl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.fdwowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              (
                SELECT pg_catalog.jsonb_build_array(
                  namespace.nspname, function_object.proname,
                  pg_catalog.pg_get_function_identity_arguments(
                    function_object.oid
                  )
                )
                FROM pg_catalog.pg_proc function_object
                JOIN pg_catalog.pg_namespace namespace
                  ON namespace.oid = function_object.pronamespace
                WHERE function_object.oid = object.fdwhandler
              ),
              (
                SELECT pg_catalog.jsonb_build_array(
                  namespace.nspname, function_object.proname,
                  pg_catalog.pg_get_function_identity_arguments(
                    function_object.oid
                  )
                )
                FROM pg_catalog.pg_proc function_object
                JOIN pg_catalog.pg_namespace namespace
                  ON namespace.oid = function_object.pronamespace
                WHERE function_object.oid = object.fdwvalidator
              ),
              COALESCE((
                SELECT pg_catalog.jsonb_agg(
                  option ORDER BY option COLLATE "C"
                )
                FROM pg_catalog.unnest(object.fdwoptions) option
              ), '[]'::pg_catalog.jsonb)
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_foreign_data_wrapper object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.fdwowner
        UNION ALL
        SELECT 'foreign_server', object.srvname, object.srvowner,
          object.srvacl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.srvowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              object.srvtype, object.srvversion,
              wrapper.fdwname,
              COALESCE((
                SELECT pg_catalog.jsonb_agg(
                  option ORDER BY option COLLATE "C"
                )
                FROM pg_catalog.unnest(object.srvoptions) option
              ), '[]'::pg_catalog.jsonb)
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_foreign_server object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.srvowner
        LEFT JOIN pg_catalog.pg_foreign_data_wrapper wrapper
          ON wrapper.oid = object.srvfdw
        UNION ALL
        SELECT 'parameter', object.parname, 10::pg_catalog.oid, object.paracl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array('<bootstrap-superuser>')::text,
            'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_parameter_acl object
        UNION ALL
        SELECT 'tablespace', object.spcname, object.spcowner, object.spcacl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.spcowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_tablespace object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.spcowner
        UNION ALL
        SELECT 'large_object', object.oid::text, object.lomowner, object.lomacl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.lomowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_largeobject_metadata object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.lomowner
      ) global_object
      CROSS JOIN LATERAL pg_catalog.aclexplode(global_object.acl) acl
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = acl.grantor
      WHERE acl.grantee = selected.boundary_oid
         OR acl.grantor = selected.boundary_oid
    ),
    application_acl_rows AS MATERIALIZED (
      SELECT pg_catalog.jsonb_build_array(
        'relation',
        pg_catalog.jsonb_build_array(
          object.nspname, object.relname, object.relkind
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = object.relowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = object.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        object.semantic_sha256
      )::text AS entry,
      privilege.grantee AS grantee_oid,
      privilege.grantor AS grantor_oid,
      object.relowner AS owner_oid,
      'relation'::text AS object_class,
      privilege.privilege_type,
      privilege.is_grantable
      FROM relation_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.relacl,
        pg_catalog.acldefault(
          CASE WHEN object.relkind = 'S' THEN 's'::"char"
            ELSE 'r'::"char" END,
          object.relowner
        )
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantee
        ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor
      WHERE object.nspname !~ '^pg_'
        AND object.nspname <> 'information_schema'

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'column',
        pg_catalog.jsonb_build_array(
          relation.nspname, relation.relname, attribute.attnum,
          attribute.attname
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = relation.relowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = relation.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        relation.semantic_sha256
      )::text,
      privilege.grantee,
      privilege.grantor,
      relation.relowner,
      'column'::text,
      privilege.privilege_type,
      privilege.is_grantable
      FROM pg_catalog.pg_attribute attribute
      JOIN relation_catalog relation ON relation.oid = attribute.attrelid
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) privilege
      LEFT JOIN pg_catalog.pg_roles grantee
        ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor
      WHERE relation.nspname !~ '^pg_'
        AND relation.nspname <> 'information_schema'

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'schema', object.nspname,
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = object.nspowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = object.nspowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE WHEN object.nspowner = selected.database_owner_oid
              THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>') END
          )::text, 'UTF8'
        )), 'hex')
      )::text,
      privilege.grantee,
      privilege.grantor,
      object.nspowner,
      'schema'::text,
      privilege.privilege_type,
      privilege.is_grantable
      FROM pg_catalog.pg_namespace object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.nspacl,
        pg_catalog.acldefault('n'::"char", object.nspowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.nspowner
      LEFT JOIN pg_catalog.pg_roles grantee
        ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor
      WHERE object.nspname !~ '^pg_'
        AND object.nspname <> 'information_schema'

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'function',
        pg_catalog.jsonb_build_array(
          object.nspname, object.proname, object.identity_arguments,
          object.prokind
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = object.proowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = object.proowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        object.semantic_sha256
      )::text,
      privilege.grantee,
      privilege.grantor,
      object.proowner,
      'function'::text,
      privilege.privilege_type,
      privilege.is_grantable
      FROM callable_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.proacl,
        pg_catalog.acldefault('f'::"char", object.proowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantee
        ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor
      WHERE object.nspname !~ '^pg_'
        AND object.nspname <> 'information_schema'

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'type',
        pg_catalog.jsonb_build_array(object.nspname, object.typname),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = object.typowner THEN '<object-owner>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = object.typowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        object.semantic_sha256
      )::text,
      privilege.grantee,
      privilege.grantor,
      object.typowner,
      'type'::text,
      privilege.privilege_type,
      privilege.is_grantable
      FROM application_type_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.typacl,
        pg_catalog.acldefault('T'::"char", object.typowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantee
        ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'database', '<current>',
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = object.datdba THEN '<object-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = object.datdba THEN '<object-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type,
        privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            '<current-db-owner>',
            object.datallowconn,
            object.datconnlimit,
            database_tablespace.spcname
          )::text, 'UTF8'
        )), 'hex')
      )::text,
      privilege.grantee,
      privilege.grantor,
      object.datdba,
      'database'::text,
      privilege.privilege_type,
      privilege.is_grantable
      FROM pg_catalog.pg_database object
      JOIN selected ON selected.database_oid = object.oid
      JOIN pg_catalog.pg_tablespace database_tablespace
        ON database_tablespace.oid = object.dattablespace
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.datacl,
        pg_catalog.acldefault('d'::"char", object.datdba)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantee
        ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor
    ),
    application_acl_manifest AS MATERIALIZED (
      SELECT application_acl_rows.entry
      FROM application_acl_rows

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'extension', namespace.nspname, object.extname, object.extversion,
        object.extrelocatable
      )::text
      FROM pg_catalog.pg_extension object
      JOIN pg_catalog.pg_namespace namespace
        ON namespace.oid = object.extnamespace
      WHERE namespace.nspname !~ '^pg_'
        AND namespace.nspname <> 'information_schema'
    ),
    application_public_manifest AS MATERIALIZED (
      SELECT pg_catalog.jsonb_build_array(
        'relation',
        pg_catalog.jsonb_build_array(
          object.nspname, object.relname, object.relkind
        ), '<public>',
        CASE
          WHEN privilege.grantor = object.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        object.semantic_sha256
      )::text AS entry
      FROM relation_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.relacl,
        pg_catalog.acldefault(
          CASE WHEN object.relkind = 'S' THEN 's'::"char"
            ELSE 'r'::"char" END,
          object.relowner
        )
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE object.nspname !~ '^pg_'
        AND object.nspname <> 'information_schema'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'column',
        pg_catalog.jsonb_build_array(
          relation.nspname, relation.relname, attribute.attnum,
          attribute.attname
        ), '<public>',
        CASE
          WHEN privilege.grantor = relation.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        relation.semantic_sha256
      )::text
      FROM pg_catalog.pg_attribute attribute
      JOIN relation_catalog relation ON relation.oid = attribute.attrelid
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) privilege
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE relation.nspname !~ '^pg_'
        AND relation.nspname <> 'information_schema'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'schema', object.nspname, '<public>',
        CASE
          WHEN privilege.grantor = object.nspowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE WHEN object.nspowner = selected.database_owner_oid
              THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>') END
          )::text, 'UTF8'
        )), 'hex')
      )::text
      FROM pg_catalog.pg_namespace object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.nspacl, pg_catalog.acldefault('n'::"char", object.nspowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.nspowner
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE object.nspname !~ '^pg_'
        AND object.nspname <> 'information_schema'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'function',
        pg_catalog.jsonb_build_array(
          object.nspname, object.proname, object.identity_arguments,
          object.prokind
        ), '<public>',
        CASE
          WHEN privilege.grantor = object.proowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        object.semantic_sha256
      )::text
      FROM callable_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.proacl,
        pg_catalog.acldefault('f'::"char", object.proowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE object.nspname !~ '^pg_'
        AND object.nspname <> 'information_schema'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'type',
        pg_catalog.jsonb_build_array(namespace.nspname, object.typname),
        '<public>',
        CASE
          WHEN privilege.grantor = object.typowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE WHEN object.typowner = selected.database_owner_oid
              THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
            object.typtype, object.typcategory, object.typispreferred,
            object.typnotnull,
            object.typlen,
            object.typbyval,
            object.typalign,
            object.typstorage,
            object.typndims,
            CASE WHEN object.typbasetype = 0 THEN NULL
              ELSE pg_catalog.format_type(
                object.typbasetype, object.typtypmod
              ) END,
            CASE WHEN object.typelem = 0 THEN NULL
              ELSE pg_catalog.format_type(object.typelem, NULL) END,
            object.typdefault,
            pg_catalog.pg_get_expr(object.typdefaultbin, 0, FALSE),
            (
              SELECT pg_catalog.jsonb_build_array(
                collation_namespace.nspname, collation_object.collname
              )
              FROM pg_catalog.pg_collation collation_object
              JOIN pg_catalog.pg_namespace collation_namespace
                ON collation_namespace.oid = collation_object.collnamespace
              WHERE collation_object.oid = object.typcollation
            ),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  enum_value.enumlabel,
                  enum_value.enumsortorder::TEXT
                ) ORDER BY enum_value.enumsortorder, enum_value.oid
              )
              FROM pg_catalog.pg_enum enum_value
              WHERE enum_value.enumtypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  domain_constraint.conname,
                  domain_constraint.condeferrable,
                  domain_constraint.condeferred,
                  domain_constraint.convalidated,
                  pg_catalog.pg_get_constraintdef(
                    domain_constraint.oid, FALSE
                  )
                ) ORDER BY domain_constraint.conname COLLATE "C"
              )
              FROM pg_catalog.pg_constraint domain_constraint
              WHERE domain_constraint.contypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            (
              SELECT pg_catalog.jsonb_build_array(
                pg_catalog.format_type(range_type.rngsubtype, NULL),
                pg_catalog.format_type(range_type.rngmultitypid, NULL),
                range_collation_namespace.nspname,
                range_collation.collname,
                range_opclass_namespace.nspname,
                range_opclass.opcname,
                canonical_namespace.nspname,
                canonical_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  canonical_function.oid
                ),
                subdiff_namespace.nspname,
                subdiff_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  subdiff_function.oid
                )
              )
              FROM pg_catalog.pg_range range_type
              JOIN pg_catalog.pg_opclass range_opclass
                ON range_opclass.oid = range_type.rngsubopc
              JOIN pg_catalog.pg_namespace range_opclass_namespace
                ON range_opclass_namespace.oid = range_opclass.opcnamespace
              LEFT JOIN pg_catalog.pg_collation range_collation
                ON range_collation.oid = range_type.rngcollation
              LEFT JOIN pg_catalog.pg_namespace range_collation_namespace
                ON range_collation_namespace.oid =
                    range_collation.collnamespace
              LEFT JOIN pg_catalog.pg_proc canonical_function
                ON canonical_function.oid = range_type.rngcanonical
              LEFT JOIN pg_catalog.pg_namespace canonical_namespace
                ON canonical_namespace.oid =
                    canonical_function.pronamespace
              LEFT JOIN pg_catalog.pg_proc subdiff_function
                ON subdiff_function.oid = range_type.rngsubdiff
              LEFT JOIN pg_catalog.pg_namespace subdiff_namespace
                ON subdiff_namespace.oid = subdiff_function.pronamespace
              WHERE range_type.rngtypid = object.oid
            ),
            extension.extname, extension.extversion
          )::text, 'UTF8'
        )), 'hex')
      )::text
      FROM pg_catalog.pg_type object
      JOIN pg_catalog.pg_namespace namespace ON namespace.oid = object.typnamespace
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.typacl,
        pg_catalog.acldefault('T'::"char", object.typowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.typowner
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      LEFT JOIN pg_catalog.pg_depend extension_dependency
        ON extension_dependency.classid = 'pg_catalog.pg_type'::pg_catalog.regclass
       AND extension_dependency.objid = object.oid
       AND extension_dependency.objsubid = 0
       AND extension_dependency.refclassid =
           'pg_catalog.pg_extension'::pg_catalog.regclass
       AND extension_dependency.deptype = 'e'
      LEFT JOIN pg_catalog.pg_extension extension
        ON extension.oid = extension_dependency.refobjid
      WHERE namespace.nspname !~ '^pg_'
        AND namespace.nspname <> 'information_schema'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'extension', namespace.nspname, object.extname, object.extversion
      )::text
      FROM pg_catalog.pg_extension object
      JOIN pg_catalog.pg_namespace namespace ON namespace.oid = object.extnamespace
      WHERE namespace.nspname !~ '^pg_'
        AND namespace.nspname <> 'information_schema'

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        class_name, identity, '<public>',
        CASE
          WHEN acl.grantor = owner_oid THEN '<object-owner>'
          WHEN acl.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', acl.grantor))
        END,
        acl.privilege_type, acl.is_grantable, semantic_sha256
      )::text
      FROM selected
      CROSS JOIN LATERAL (
        SELECT 'database'::text AS class_name, '<current>'::text AS identity,
          object.datdba AS owner_oid,
          COALESCE(object.datacl,
            pg_catalog.acldefault('d'::"char", object.datdba)) AS acl,
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.datdba = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              object.datallowconn, object.datconnlimit
            )::text, 'UTF8'
          )), 'hex') AS semantic_sha256
        FROM pg_catalog.pg_database object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.datdba
        WHERE object.oid = selected.database_oid
        UNION ALL
        SELECT 'language', object.lanname, object.lanowner,
          COALESCE(object.lanacl,
            pg_catalog.acldefault('l'::"char", object.lanowner)),
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.lanowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              object.lanpltrusted
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_language object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.lanowner
        UNION ALL
        SELECT 'foreign_data_wrapper', object.fdwname, object.fdwowner,
          COALESCE(object.fdwacl,
            pg_catalog.acldefault('F'::"char", object.fdwowner)),
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.fdwowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              (
                SELECT pg_catalog.jsonb_build_array(
                  namespace.nspname, function_object.proname,
                  pg_catalog.pg_get_function_identity_arguments(
                    function_object.oid
                  )
                )
                FROM pg_catalog.pg_proc function_object
                JOIN pg_catalog.pg_namespace namespace
                  ON namespace.oid = function_object.pronamespace
                WHERE function_object.oid = object.fdwhandler
              ),
              (
                SELECT pg_catalog.jsonb_build_array(
                  namespace.nspname, function_object.proname,
                  pg_catalog.pg_get_function_identity_arguments(
                    function_object.oid
                  )
                )
                FROM pg_catalog.pg_proc function_object
                JOIN pg_catalog.pg_namespace namespace
                  ON namespace.oid = function_object.pronamespace
                WHERE function_object.oid = object.fdwvalidator
              ),
              COALESCE((
                SELECT pg_catalog.jsonb_agg(
                  option ORDER BY option COLLATE "C"
                )
                FROM pg_catalog.unnest(object.fdwoptions) option
              ), '[]'::pg_catalog.jsonb)
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_foreign_data_wrapper object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.fdwowner
        UNION ALL
        SELECT 'foreign_server', object.srvname, object.srvowner,
          COALESCE(object.srvacl,
            pg_catalog.acldefault('s'::"char", object.srvowner)),
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.srvowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
              object.srvtype, object.srvversion,
              wrapper.fdwname,
              COALESCE((
                SELECT pg_catalog.jsonb_agg(
                  option ORDER BY option COLLATE "C"
                )
                FROM pg_catalog.unnest(object.srvoptions) option
              ), '[]'::pg_catalog.jsonb)
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_foreign_server object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.srvowner
        LEFT JOIN pg_catalog.pg_foreign_data_wrapper wrapper
          ON wrapper.oid = object.srvfdw
        UNION ALL
        SELECT 'parameter', object.parname, 10::pg_catalog.oid,
          COALESCE(object.paracl,
            pg_catalog.acldefault('p'::"char", 10::pg_catalog.oid)),
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array('<bootstrap-superuser>')::text,
            'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_parameter_acl object
        UNION ALL
        SELECT 'tablespace', object.spcname, object.spcowner,
          COALESCE(object.spcacl,
            pg_catalog.acldefault('t'::"char", object.spcowner)),
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.spcowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_tablespace object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.spcowner
        UNION ALL
        SELECT 'large_object', object.oid::text, object.lomowner,
          COALESCE(object.lomacl,
            pg_catalog.acldefault('L'::"char", object.lomowner)),
          pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
              CASE WHEN object.lomowner = selected.database_owner_oid
                THEN '<current-db-owner>'
                ELSE COALESCE(owner.rolname, '<unknown-owner>') END
            )::text, 'UTF8'
          )), 'hex')
        FROM pg_catalog.pg_largeobject_metadata object
        LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.lomowner
      ) global_object
      CROSS JOIN LATERAL pg_catalog.aclexplode(global_object.acl) acl
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = acl.grantor
      WHERE acl.grantee = 0
    ),
    system_public_manifest AS MATERIALIZED (
      SELECT pg_catalog.jsonb_build_array(
        'relation',
        pg_catalog.jsonb_build_array(
          object.nspname, object.relname, object.relkind
        ), '<public>',
        CASE
          WHEN privilege.grantor = object.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        object.semantic_sha256
      )::text AS entry
      FROM relation_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.relacl,
        pg_catalog.acldefault(
          CASE WHEN object.relkind = 'S' THEN 's'::"char"
            ELSE 'r'::"char" END,
          object.relowner
        )
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE (object.nspname ~ '^pg_'
          OR object.nspname = 'information_schema')
        AND object.nspname !~ '^pg_temp_[0-9]+$'
        AND object.nspname !~ '^pg_toast_temp_[0-9]+$'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'column',
        pg_catalog.jsonb_build_array(
          relation.nspname, relation.relname, attribute.attnum,
          attribute.attname
        ), '<public>',
        CASE
          WHEN privilege.grantor = relation.relowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        relation.semantic_sha256
      )::text
      FROM pg_catalog.pg_attribute attribute
      JOIN relation_catalog relation ON relation.oid = attribute.attrelid
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) privilege
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE (relation.nspname ~ '^pg_'
          OR relation.nspname = 'information_schema')
        AND relation.nspname !~ '^pg_temp_[0-9]+$'
        AND relation.nspname !~ '^pg_toast_temp_[0-9]+$'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'schema', object.nspname, '<public>',
        CASE
          WHEN privilege.grantor = object.nspowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE WHEN object.nspowner = selected.database_owner_oid
              THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>') END
          )::text, 'UTF8'
        )), 'hex')
      )::text
      FROM pg_catalog.pg_namespace object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.nspacl, pg_catalog.acldefault('n'::"char", object.nspowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.nspowner
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE (object.nspname ~ '^pg_'
          OR object.nspname = 'information_schema')
        AND object.nspname !~ '^pg_temp_[0-9]+$'
        AND object.nspname !~ '^pg_toast_temp_[0-9]+$'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'function',
        pg_catalog.jsonb_build_array(
          object.nspname, object.proname, object.identity_arguments,
          object.prokind
        ), '<public>',
        CASE
          WHEN privilege.grantor = object.proowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        object.semantic_sha256
      )::text
      FROM callable_catalog object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.proacl,
        pg_catalog.acldefault('f'::"char", object.proowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      WHERE (object.nspname ~ '^pg_'
          OR object.nspname = 'information_schema')
        AND object.nspname !~ '^pg_temp_[0-9]+$'
        AND object.nspname !~ '^pg_toast_temp_[0-9]+$'
        AND privilege.grantee = 0

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'type',
        pg_catalog.jsonb_build_array(namespace.nspname, object.typname),
        '<public>',
        CASE
          WHEN privilege.grantor = object.typowner THEN '<object-owner>'
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
          pg_catalog.jsonb_build_array(
            CASE WHEN object.typowner = selected.database_owner_oid
              THEN '<current-db-owner>'
              ELSE COALESCE(owner.rolname, '<unknown-owner>') END,
            object.typtype, object.typcategory, object.typispreferred,
            object.typnotnull,
            object.typlen,
            object.typbyval,
            object.typalign,
            object.typstorage,
            object.typndims,
            CASE WHEN object.typbasetype = 0 THEN NULL
              ELSE pg_catalog.format_type(
                object.typbasetype, object.typtypmod
              ) END,
            CASE WHEN object.typelem = 0 THEN NULL
              ELSE pg_catalog.format_type(object.typelem, NULL) END,
            object.typdefault,
            pg_catalog.pg_get_expr(object.typdefaultbin, 0, FALSE),
            (
              SELECT pg_catalog.jsonb_build_array(
                collation_namespace.nspname, collation_object.collname
              )
              FROM pg_catalog.pg_collation collation_object
              JOIN pg_catalog.pg_namespace collation_namespace
                ON collation_namespace.oid = collation_object.collnamespace
              WHERE collation_object.oid = object.typcollation
            ),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  enum_value.enumlabel,
                  enum_value.enumsortorder::TEXT
                ) ORDER BY enum_value.enumsortorder, enum_value.oid
              )
              FROM pg_catalog.pg_enum enum_value
              WHERE enum_value.enumtypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            COALESCE((
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                  domain_constraint.conname,
                  domain_constraint.condeferrable,
                  domain_constraint.condeferred,
                  domain_constraint.convalidated,
                  pg_catalog.pg_get_constraintdef(
                    domain_constraint.oid, FALSE
                  )
                ) ORDER BY domain_constraint.conname COLLATE "C"
              )
              FROM pg_catalog.pg_constraint domain_constraint
              WHERE domain_constraint.contypid = object.oid
            ), '[]'::pg_catalog.jsonb),
            (
              SELECT pg_catalog.jsonb_build_array(
                pg_catalog.format_type(range_type.rngsubtype, NULL),
                pg_catalog.format_type(range_type.rngmultitypid, NULL),
                range_collation_namespace.nspname,
                range_collation.collname,
                range_opclass_namespace.nspname,
                range_opclass.opcname,
                canonical_namespace.nspname,
                canonical_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  canonical_function.oid
                ),
                subdiff_namespace.nspname,
                subdiff_function.proname,
                pg_catalog.pg_get_function_identity_arguments(
                  subdiff_function.oid
                )
              )
              FROM pg_catalog.pg_range range_type
              JOIN pg_catalog.pg_opclass range_opclass
                ON range_opclass.oid = range_type.rngsubopc
              JOIN pg_catalog.pg_namespace range_opclass_namespace
                ON range_opclass_namespace.oid = range_opclass.opcnamespace
              LEFT JOIN pg_catalog.pg_collation range_collation
                ON range_collation.oid = range_type.rngcollation
              LEFT JOIN pg_catalog.pg_namespace range_collation_namespace
                ON range_collation_namespace.oid =
                    range_collation.collnamespace
              LEFT JOIN pg_catalog.pg_proc canonical_function
                ON canonical_function.oid = range_type.rngcanonical
              LEFT JOIN pg_catalog.pg_namespace canonical_namespace
                ON canonical_namespace.oid =
                    canonical_function.pronamespace
              LEFT JOIN pg_catalog.pg_proc subdiff_function
                ON subdiff_function.oid = range_type.rngsubdiff
              LEFT JOIN pg_catalog.pg_namespace subdiff_namespace
                ON subdiff_namespace.oid = subdiff_function.pronamespace
              WHERE range_type.rngtypid = object.oid
            ),
            extension.extname, extension.extversion
          )::text, 'UTF8'
        )), 'hex')
      )::text
      FROM pg_catalog.pg_type object
      JOIN pg_catalog.pg_namespace namespace ON namespace.oid = object.typnamespace
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        object.typacl,
        pg_catalog.acldefault('T'::"char", object.typowner)
      )) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.typowner
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
      LEFT JOIN pg_catalog.pg_depend extension_dependency
        ON extension_dependency.classid = 'pg_catalog.pg_type'::pg_catalog.regclass
       AND extension_dependency.objid = object.oid
       AND extension_dependency.objsubid = 0
       AND extension_dependency.refclassid =
           'pg_catalog.pg_extension'::pg_catalog.regclass
       AND extension_dependency.deptype = 'e'
      LEFT JOIN pg_catalog.pg_extension extension
        ON extension.oid = extension_dependency.refobjid
      WHERE (namespace.nspname ~ '^pg_'
          OR namespace.nspname = 'information_schema')
        AND namespace.nspname !~ '^pg_temp_[0-9]+$'
        AND namespace.nspname !~ '^pg_toast_temp_[0-9]+$'
        AND privilege.grantee = 0
    ),
    future_default_acl_manifest AS MATERIALIZED (
      SELECT pg_catalog.jsonb_build_array(
        'default_acl_row',
        CASE WHEN object.defaclrole = selected.database_owner_oid
          THEN '<current-db-owner>'
          ELSE COALESCE(owner.rolname,
            pg_catalog.format('<oid:%s>', object.defaclrole)) END,
        COALESCE(namespace.nspname, '<global>'), object.defaclobjtype
      )::text AS entry
      FROM pg_catalog.pg_default_acl object
      JOIN selected ON TRUE
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.defaclrole
      LEFT JOIN pg_catalog.pg_namespace namespace
        ON namespace.oid = object.defaclnamespace

      UNION ALL
      SELECT pg_catalog.jsonb_build_array(
        'default_acl_item',
        pg_catalog.jsonb_build_array(
          CASE WHEN object.defaclrole = selected.database_owner_oid
            THEN '<current-db-owner>'
            ELSE COALESCE(owner.rolname,
              pg_catalog.format('<oid:%s>', object.defaclrole)) END,
          COALESCE(namespace.nspname, '<global>'), object.defaclobjtype
        ),
        CASE
          WHEN privilege.grantee = 0 THEN '<public>'
          WHEN privilege.grantee = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantee.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantee))
        END,
        CASE
          WHEN privilege.grantor = selected.database_owner_oid
            THEN '<current-db-owner>'
          ELSE COALESCE(grantor.rolname,
            pg_catalog.format('<oid:%s>', privilege.grantor))
        END,
        privilege.privilege_type, privilege.is_grantable
      )::text
      FROM pg_catalog.pg_default_acl object
      JOIN selected ON TRUE
      CROSS JOIN LATERAL pg_catalog.aclexplode(object.defaclacl) privilege
      LEFT JOIN pg_catalog.pg_roles owner ON owner.oid = object.defaclrole
      LEFT JOIN pg_catalog.pg_namespace namespace
        ON namespace.oid = object.defaclnamespace
      LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = privilege.grantee
      LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid = privilege.grantor
    )
    SELECT pg_catalog.current_setting('server_version_num')::integer
        AS "serverVersionNumber",
      session_user::text AS "sessionRole",
      selected.original_search_path::text AS "sessionSearchPath",
      login.rolname::text AS "loginRole",
      login.rolcanlogin AS "loginCanLogin",
      login.rolsuper AS "loginSuperuser",
      login.rolcreatedb AS "loginCreateDb",
      login.rolcreaterole AS "loginCreateRole",
      login.rolinherit AS "loginInherits",
      login.rolreplication AS "loginReplication",
      login.rolbypassrls AS "loginBypassRls",
      login.rolconnlimit AS "loginConnectionLimit",
      login.rolvaliduntil AS "loginValidUntil",
      public.quillmd_boundary_password_is_null(login.rolname)
        AS "loginHasExactVerifier",
      ARRAY(
        SELECT granted.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles granted ON granted.oid = membership.roleid
        WHERE membership.member = login.oid
        ORDER BY granted.rolname COLLATE "C"
      ) AS "loginMemberships",
      EXISTS(
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.member = login.oid AND membership.admin_option
      ) AS "loginHasAdminMembership",
      EXISTS(
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.member = login.oid
          AND membership.inherit_option = FALSE
      ) AS "loginHasNonInheritedMembership",
      EXISTS(
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.member = login.oid AND membership.set_option
      ) AS "loginHasSetMembership",
      EXISTS(
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles grantor ON grantor.oid = membership.grantor
        WHERE membership.member = login.oid AND grantor.rolsuper = FALSE
      ) AS "loginHasNonSuperuserGrantor",
      ARRAY(
        SELECT member.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member ON member.oid = membership.member
        WHERE membership.roleid = login.oid
        ORDER BY member.rolname COLLATE "C"
      ) AS "loginMembers",
      (
        login.rolconfig IS NOT NULL
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = login.oid
        )
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = login.oid
        )
      ) AS "loginHasDirectAuthority",
      boundary.rolname::text AS "boundaryRole",
      boundary.rolcanlogin AS "boundaryCanLogin",
      boundary.rolsuper AS "boundarySuperuser",
      boundary.rolcreatedb AS "boundaryCreateDb",
      boundary.rolcreaterole AS "boundaryCreateRole",
      boundary.rolinherit AS "boundaryInherits",
      boundary.rolreplication AS "boundaryReplication",
      boundary.rolbypassrls AS "boundaryBypassRls",
      boundary.rolconnlimit AS "boundaryConnectionLimit",
      boundary.rolvaliduntil AS "boundaryValidUntil",
      ARRAY(
        SELECT member.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member ON member.oid = membership.member
        WHERE membership.roleid = boundary.oid
        ORDER BY member.rolname COLLATE "C"
      ) AS "boundaryMembers",
      EXISTS(
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.roleid = boundary.oid AND membership.admin_option
      ) AS "boundaryHasAdminMember",
      EXISTS(
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.roleid = boundary.oid
          AND membership.inherit_option = FALSE
      ) AS "boundaryHasNonInheritedMember",
      EXISTS(
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.roleid = boundary.oid AND membership.set_option
      ) AS "boundaryHasSetMember",
      EXISTS(
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles grantor ON grantor.oid = membership.grantor
        WHERE membership.roleid = boundary.oid AND grantor.rolsuper = FALSE
      ) AS "boundaryHasNonSuperuserGrantor",
      ARRAY(
        SELECT granted.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles granted ON granted.oid = membership.roleid
        WHERE membership.member = boundary.oid
        ORDER BY granted.rolname COLLATE "C"
      ) AS "boundaryMemberships",
      EXISTS (
        SELECT 1
        FROM pg_catalog.pg_roles read_all_data
        WHERE read_all_data.rolname = 'pg_read_all_data'
          AND read_all_data.rolcanlogin = FALSE
          AND read_all_data.rolsuper = FALSE
          AND read_all_data.rolcreatedb = FALSE
          AND read_all_data.rolcreaterole = FALSE
          AND read_all_data.rolinherit = TRUE
          AND read_all_data.rolreplication = FALSE
          AND read_all_data.rolbypassrls = FALSE
          AND read_all_data.rolconnlimit = -1
          AND read_all_data.rolvaliduntil IS NULL
          AND read_all_data.rolconfig IS NULL
          AND (
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_auth_members membership
            WHERE membership.member = read_all_data.oid
               OR membership.roleid = read_all_data.oid
               OR membership.grantor = read_all_data.oid
          ) = 1
          AND EXISTS (
            SELECT 1
            FROM pg_catalog.pg_auth_members membership
            JOIN pg_catalog.pg_roles member_role
              ON member_role.oid = membership.member
            JOIN pg_catalog.pg_roles grantor_role
              ON grantor_role.oid = membership.grantor
            WHERE membership.roleid = read_all_data.oid
              AND member_role.rolname = 'quillmd_backup'
              AND membership.admin_option = FALSE
              AND membership.inherit_option = TRUE
              AND membership.set_option = FALSE
              AND grantor_role.rolsuper = TRUE
          )
      ) AS "readAllDataClosureIsExact",
      (
        public.quillmd_boundary_password_is_null(boundary.rolname)
          IS DISTINCT FROM TRUE
      ) AS "boundaryHasPassword",
      (SELECT pg_catalog.count(*)::integer FROM boundary_manifest)
        AS "boundaryAclCount",
      (SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        COALESCE(pg_catalog.string_agg(
          manifest.entry, E'\n' ORDER BY manifest.entry COLLATE "C"
        ), ''), 'UTF8'
      )), 'hex') FROM boundary_manifest manifest) AS "boundaryAclSha256",
      CASE WHEN ${input.includeManifestEntries === true}
        THEN ARRAY(
          SELECT manifest.entry
          FROM boundary_manifest manifest
          ORDER BY manifest.entry COLLATE "C"
        )
        ELSE ARRAY[]::TEXT[]
      END AS "boundaryAclManifest",
      (SELECT pg_catalog.count(*)::integer FROM application_acl_manifest)
        AS "applicationAclCount",
      (SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        COALESCE(pg_catalog.string_agg(
          manifest.entry, E'\n' ORDER BY manifest.entry COLLATE "C"
        ), ''), 'UTF8'
      )), 'hex') FROM application_acl_manifest manifest)
        AS "applicationAclSha256",
      CASE WHEN ${input.includeManifestEntries === true}
        THEN ARRAY(
          SELECT manifest.entry
          FROM application_acl_manifest manifest
          ORDER BY manifest.entry COLLATE "C"
        )
        ELSE ARRAY[]::TEXT[]
      END AS "applicationAclManifest",
      (SELECT pg_catalog.count(*)::integer FROM application_public_manifest)
        AS "applicationPublicAclCount",
      (SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        COALESCE(pg_catalog.string_agg(
          manifest.entry, E'\n' ORDER BY manifest.entry COLLATE "C"
        ), ''), 'UTF8'
      )), 'hex') FROM application_public_manifest manifest)
        AS "applicationPublicAclSha256",
      CASE WHEN ${input.includeManifestEntries === true}
        THEN ARRAY(
          SELECT manifest.entry
          FROM application_public_manifest manifest
          ORDER BY manifest.entry COLLATE "C"
        )
        ELSE ARRAY[]::TEXT[]
      END AS "applicationPublicAclManifest",
      (SELECT pg_catalog.count(*)::integer FROM system_public_manifest)
        AS "systemPublicAclCount",
      (SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        COALESCE(pg_catalog.string_agg(
          manifest.entry, E'\n' ORDER BY manifest.entry COLLATE "C"
        ), ''), 'UTF8'
      )), 'hex') FROM system_public_manifest manifest)
        AS "systemPublicAclSha256",
      CASE WHEN ${input.includeManifestEntries === true}
        THEN ARRAY(
          SELECT manifest.entry
          FROM system_public_manifest manifest
          ORDER BY manifest.entry COLLATE "C"
        )
        ELSE ARRAY[]::TEXT[]
      END AS "systemPublicAclManifest",
      (SELECT pg_catalog.count(*)::integer FROM future_default_acl_manifest)
        AS "futureDefaultAclCount",
      (SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        COALESCE(pg_catalog.string_agg(
          manifest.entry, E'\n' ORDER BY manifest.entry COLLATE "C"
        ), ''), 'UTF8'
      )), 'hex') FROM future_default_acl_manifest manifest)
        AS "futureDefaultAclSha256",
      CASE WHEN ${input.includeManifestEntries === true}
        THEN ARRAY(
          SELECT manifest.entry
          FROM future_default_acl_manifest manifest
          ORDER BY manifest.entry COLLATE "C"
        )
        ELSE ARRAY[]::TEXT[]
      END AS "futureDefaultAclManifest",
      (
        boundary.rolconfig IS NOT NULL
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = boundary.oid
        )
        OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_shdepend dependency
          JOIN selected ON TRUE
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = boundary.oid
            AND NOT (
              dependency.deptype = 'a'
              AND (
                (
                  dependency.dbid = selected.database_oid
                  AND dependency.classid IN (
                    'pg_catalog.pg_class'::pg_catalog.regclass,
                    'pg_catalog.pg_default_acl'::pg_catalog.regclass,
                    'pg_catalog.pg_foreign_data_wrapper'::pg_catalog.regclass,
                    'pg_catalog.pg_foreign_server'::pg_catalog.regclass,
                    'pg_catalog.pg_language'::pg_catalog.regclass,
                    'pg_catalog.pg_largeobject_metadata'::pg_catalog.regclass,
                    'pg_catalog.pg_namespace'::pg_catalog.regclass,
                    'pg_catalog.pg_proc'::pg_catalog.regclass,
                    'pg_catalog.pg_type'::pg_catalog.regclass
                  )
                ) OR (
                  dependency.dbid = 0
                  AND (
                    (dependency.classid =
                       'pg_catalog.pg_database'::pg_catalog.regclass
                     AND dependency.objid = selected.database_oid)
                    OR dependency.classid IN (
                      'pg_catalog.pg_parameter_acl'::pg_catalog.regclass,
                      'pg_catalog.pg_tablespace'::pg_catalog.regclass
                    )
                  )
                )
              )
            )
        )
      ) AS "boundaryHasUnexpectedDependency",
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members membership
        WHERE membership.grantor IN (login.oid, boundary.oid)
      ) AS "graphHasForbiddenGrantor",
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_db_role_setting setting
        WHERE setting.setrole = 0
      ) AS "databaseHasGlobalRoleSettings",
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_policy policy
        WHERE 0::pg_catalog.oid = ANY(policy.polroles)
           OR boundary.oid = ANY(policy.polroles)
      ) AS "hasApplicablePolicy",
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_user_mappings mapping
        WHERE mapping.umuser = 0
      ) AS "hasPublicUserMapping",
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_user_mappings mapping
        WHERE mapping.umuser = boundary.oid
      ) AS "hasBoundaryUserMapping",
      (
        EXISTS (
          SELECT 1
          FROM pg_catalog.pg_class foreign_table
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            foreign_table.relacl,
            pg_catalog.acldefault('r'::"char", foreign_table.relowner)
          )) privilege
          WHERE foreign_table.relkind = 'f'
            AND (
              privilege.grantee IN (0, boundary.oid)
              OR privilege.grantor = boundary.oid
            )
        ) OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_foreign_data_wrapper wrapper
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            wrapper.fdwacl,
            pg_catalog.acldefault('F'::"char", wrapper.fdwowner)
          )) privilege
          WHERE privilege.grantee IN (0, boundary.oid)
             OR privilege.grantor = boundary.oid
        ) OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_foreign_server server
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            server.srvacl,
            pg_catalog.acldefault('s'::"char", server.srvowner)
          )) privilege
          WHERE privilege.grantee IN (0, boundary.oid)
             OR privilege.grantor = boundary.oid
        )
      ) AS "hasForeignDataAuthority",
      EXISTS (
        SELECT 1
        FROM pg_catalog.pg_namespace namespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
          namespace.nspacl,
          pg_catalog.acldefault('n'::"char", namespace.nspowner)
        )) privilege
        WHERE namespace.nspname !~ '^pg_'
          AND namespace.nspname <> 'information_schema'
          AND privilege.privilege_type = 'CREATE'
          AND (privilege.grantee = 0 OR privilege.grantee = boundary.oid)
      ) AS "hasWritableApplicationSchema",
      (
        EXISTS (
          SELECT 1
          FROM application_acl_rows application_acl
          WHERE NOT (
            application_acl.grantee_oid = 0
            OR application_acl.grantee_oid = selected.database_owner_oid
            OR EXISTS (
              SELECT 1
              FROM pg_catalog.pg_roles approved_grantee
              WHERE approved_grantee.oid = application_acl.grantee_oid
                AND approved_grantee.rolname IN (
                  'pg_database_owner',
                  'quillmd_runtime',
                  'quillmd_release_control',
                  'quillmd_release_security',
                  'quillmd_audit_dispatcher',
                  'quillmd_auth_email_dispatcher',
                  'quillmd_backup'
                )
            )
          )
        )
        OR EXISTS (
          SELECT 1
          FROM application_acl_rows application_acl
          WHERE application_acl.grantor_oid <> selected.database_owner_oid
            AND NOT EXISTS (
              SELECT 1
              FROM pg_catalog.pg_roles approved_grantor
              WHERE approved_grantor.oid = application_acl.grantor_oid
                AND approved_grantor.rolname = 'pg_database_owner'
            )
        )
        OR EXISTS (
          SELECT 1
          FROM relation_catalog object
          WHERE object.nspname !~ '^pg_'
            AND object.nspname <> 'information_schema'
            AND object.relowner <> selected.database_owner_oid
        )
        OR EXISTS (
          SELECT 1
          FROM callable_catalog object
          WHERE object.nspname !~ '^pg_'
            AND object.nspname <> 'information_schema'
            AND object.proowner <> selected.database_owner_oid
        )
        OR EXISTS (
          SELECT 1
          FROM application_type_catalog object
          WHERE object.typowner <> selected.database_owner_oid
        )
        OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_namespace object
          WHERE object.nspname !~ '^pg_'
            AND object.nspname <> 'information_schema'
            AND object.nspowner <> selected.database_owner_oid
            AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_roles database_owner_role
              WHERE database_owner_role.oid = object.nspowner
                AND database_owner_role.rolname = 'pg_database_owner'
            )
        )
      ) AS "hasUnapprovedApplicationAuthority",
      EXISTS (
        SELECT 1
        FROM callable_catalog callable
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
          callable.proacl,
          pg_catalog.acldefault('f'::"char", callable.proowner)
        )) privilege
        WHERE privilege.privilege_type = 'EXECUTE'
          AND (
            (
              callable.nspname !~ '^pg_'
              AND callable.nspname <> 'information_schema'
            )
            OR privilege.grantee = boundary.oid
            OR privilege.grantor = boundary.oid
          )
          AND (
            privilege.grantee = 0
            OR privilege.grantee = boundary.oid
            OR privilege.grantor = boundary.oid
          )
          AND (
            (callable.prokind IN ('a', 'w') AND callable.extname IS NULL)
            OR (
              callable.prosecdef
              AND NOT (
                callable.proconfig IS NOT NULL
                AND 'search_path=pg_catalog, public, pg_temp' =
                    ANY(callable.proconfig)
                AND (
                  SELECT pg_catalog.count(*)
                  FROM pg_catalog.unnest(callable.proconfig) setting
                  WHERE setting LIKE 'search_path=%'
                ) = 1
              )
            )
          )
      ) AS "hasUnsafeExecutableCapability",
      (
        (SELECT pg_catalog.count(*)
         FROM pg_catalog.pg_proc function_object
         WHERE function_object.oid IN (
           'pg_catalog.lo_creat(integer)'::pg_catalog.regprocedure,
           'pg_catalog.lo_create(oid)'::pg_catalog.regprocedure,
           'pg_catalog.lo_from_bytea(oid,bytea)'::pg_catalog.regprocedure,
           'pg_catalog.lo_import(text)'::pg_catalog.regprocedure,
           'pg_catalog.lo_import(text,oid)'::pg_catalog.regprocedure,
           'pg_catalog.lo_open(oid,integer)'::pg_catalog.regprocedure,
           'pg_catalog.lo_put(oid,bigint,bytea)'::pg_catalog.regprocedure,
           'pg_catalog.lo_truncate(integer,integer)'::pg_catalog.regprocedure,
           'pg_catalog.lo_truncate64(integer,bigint)'::pg_catalog.regprocedure,
           'pg_catalog.lo_unlink(oid)'::pg_catalog.regprocedure,
           'pg_catalog.lo_export(oid,text)'::pg_catalog.regprocedure,
           'pg_catalog.lowrite(integer,bytea)'::pg_catalog.regprocedure
         )) <> 12
        OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_proc function_object
          WHERE function_object.oid IN (
            'pg_catalog.lo_creat(integer)'::pg_catalog.regprocedure,
            'pg_catalog.lo_create(oid)'::pg_catalog.regprocedure,
            'pg_catalog.lo_from_bytea(oid,bytea)'::pg_catalog.regprocedure,
            'pg_catalog.lo_import(text)'::pg_catalog.regprocedure,
            'pg_catalog.lo_import(text,oid)'::pg_catalog.regprocedure,
            'pg_catalog.lo_open(oid,integer)'::pg_catalog.regprocedure,
            'pg_catalog.lo_put(oid,bigint,bytea)'::pg_catalog.regprocedure,
            'pg_catalog.lo_truncate(integer,integer)'::pg_catalog.regprocedure,
            'pg_catalog.lo_truncate64(integer,bigint)'::pg_catalog.regprocedure,
            'pg_catalog.lo_unlink(oid)'::pg_catalog.regprocedure,
            'pg_catalog.lo_export(oid,text)'::pg_catalog.regprocedure,
            'pg_catalog.lowrite(integer,bytea)'::pg_catalog.regprocedure
          ) AND (
            pg_catalog.has_function_privilege(
              login.oid, function_object.oid, 'EXECUTE'
            ) IS DISTINCT FROM FALSE
            OR pg_catalog.has_function_privilege(
              boundary.oid, function_object.oid, 'EXECUTE'
            ) IS DISTINCT FROM FALSE
            OR EXISTS (
              SELECT 1
              FROM pg_catalog.aclexplode(COALESCE(
                function_object.proacl,
                pg_catalog.acldefault(
                  'f'::"char", function_object.proowner
                )
              )) privilege
              WHERE privilege.grantee = 0
                AND privilege.privilege_type = 'EXECUTE'
            )
          )
        )
      ) AS "hasForbiddenLargeObjectFunctionAuthority",
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_largeobject_metadata
      ) AS "hasLargeObjects",
      pg_catalog.has_database_privilege(
        login.oid, selected.database_oid, 'CONNECT'
      ) AS "loginCanConnectCurrentDatabase",
      pg_catalog.has_database_privilege(
        boundary.oid, selected.database_oid, 'CONNECT'
      ) AS "boundaryCanConnectCurrentDatabase",
      (
        pg_catalog.has_database_privilege(
          login.oid, selected.database_oid, 'CREATE'
        )
        OR pg_catalog.has_database_privilege(
          login.oid, selected.database_oid, 'TEMP'
        )
        OR pg_catalog.has_database_privilege(
          boundary.oid, selected.database_oid, 'CREATE'
        )
        OR pg_catalog.has_database_privilege(
          boundary.oid, selected.database_oid, 'TEMP'
        )
        OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_database database
          WHERE database.oid <> selected.database_oid
            AND (
              pg_catalog.has_database_privilege(
                login.oid, database.oid, 'CONNECT'
              )
              OR pg_catalog.has_database_privilege(
                login.oid, database.oid, 'CREATE'
              )
              OR pg_catalog.has_database_privilege(
                login.oid, database.oid, 'TEMP'
              )
              OR pg_catalog.has_database_privilege(
                boundary.oid, database.oid, 'CONNECT'
              )
              OR pg_catalog.has_database_privilege(
                boundary.oid, database.oid, 'CREATE'
              )
              OR pg_catalog.has_database_privilege(
                boundary.oid, database.oid, 'TEMP'
              )
            )
        )
        OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_database database
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            database.datacl,
            pg_catalog.acldefault('d'::"char", database.datdba)
          )) privilege
          WHERE privilege.grantee = login.oid
             OR privilege.grantor = login.oid
        )
        OR (
          SELECT pg_catalog.count(*)
          FROM pg_catalog.pg_database database
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            database.datacl,
            pg_catalog.acldefault('d'::"char", database.datdba)
          )) privilege
          WHERE privilege.grantee = boundary.oid
             OR privilege.grantor = boundary.oid
        ) <> 1
        OR NOT EXISTS (
          SELECT 1
          FROM pg_catalog.pg_database database
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            database.datacl,
            pg_catalog.acldefault('d'::"char", database.datdba)
          )) privilege
          JOIN pg_catalog.pg_roles grantor
            ON grantor.oid = privilege.grantor
          WHERE database.oid = selected.database_oid
            AND privilege.grantee = boundary.oid
            AND privilege.privilege_type = 'CONNECT'
            AND privilege.is_grantable = FALSE
            AND grantor.rolsuper
        )
        OR EXISTS (
          SELECT 1
          FROM pg_catalog.pg_database database
          CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
            database.datacl,
            pg_catalog.acldefault('d'::"char", database.datdba)
          )) privilege
          WHERE privilege.grantee = 0
            AND privilege.privilege_type IN ('CONNECT', 'CREATE', 'TEMPORARY')
        )
      ) AS "hasForbiddenDatabaseAuthority"
    FROM pg_catalog.pg_roles login
    CROSS JOIN pg_catalog.pg_roles boundary
    JOIN selected
      ON selected.login_oid = login.oid
     AND selected.boundary_oid = boundary.oid
    WHERE (
        ${input.requireSessionRole !== false} = FALSE
        OR login.rolname = current_user
      )
      AND login.rolname = ${input.loginRole}
      AND boundary.rolname = ${input.boundaryRole}
  `;
}
