export {
  createTemplateTwinArtifactStore,
  hasTemplateTwinStorageProvider,
  TemplateTwinArtifactCollisionError,
  TemplateTwinArtifactIntegrityError,
  TemplateTwinArtifactTooLargeError,
  TemplateTwinStorageUnavailableError,
  type CreateTemplateTwinArtifactStoreOptions,
  type ReadArtifactInput,
  type StoredTemplateTwinArtifact,
  type StoreOutputArtifactInput,
  type StoreSourceArtifactInput,
  type TemplateTwinArtifactStore,
  type TemplateTwinObjectClient,
  type TemplateTwinObjectClientFactory,
} from './artifact-store';

export {
  createOutputArtifactKey,
  createSourceArtifactKey,
  DEFAULT_TEMPLATE_TWIN_BUCKET,
  DOCX_MIME_TYPE,
  InvalidTemplateTwinStorageInputError,
  resolveTemplateTwinBucket,
  templateTwinTenantPrefix,
  type TemplateTwinArtifactKind,
} from './keys';

export {
  assertTemplateTwinRecordOwner,
  assertTenantOwnedArtifactKey,
  isTemplateTwinRecordOwner,
  isTenantOwnedArtifactKey,
  parseTemplateTwinArtifactKey,
  TemplateTwinArtifactNotFoundError,
  type ParsedTemplateTwinArtifactKey,
  type TemplateTwinActor,
  type TemplateTwinOwnedRecord,
} from './ownership';
