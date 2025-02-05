from subprocess import Popen, PIPE, STDOUT
import os


class _DefaultOptions:
    """ Base class for classes that need to use options """
    # All options with default values. If a value is None, it needs to be overridden
    projectId = None
    regionId = 'europe-north1'
    serviceAccountPrefix = 'dlpflow-runner'
    tempGcsBucket = None
    workerMachineType = 'n1-standard-1'
    subnetworkName = 'dataflow-subnetwork'
    sampleSize = 100
    sourceType = 'PARQUET'
    csvFirstRowHeader = False
    csvHeaders = []
    source = None
    logFile = STDOUT
    userName = os.environ['JUPYTERHUB_USER']

    class OptionError(AttributeError): pass

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def validate(self):
        for att in dir(self):
            if not att.startswith('_') and getattr(self, att) is None:
                raise self.OptionError("missing required option: " + att)

    def init_options(self, option, kw):
        """ To be called from the derived class constructor.
        Puts the options into object scope. """
        for k, v in list(option.__dict__.items()) + list(kw.items()):
            if not hasattr(self.__class__, k):
                raise self.OptionError("invalid option: " + k)
            setattr(self, k, v)
        # Derive extra options
        if getattr(self, 'tempGcsBucket') is None:
            pid = getattr(self, 'projectId')
            setattr(self, 'tempGcsBucket', f"ssb-{pid[:pid.rindex('-')]}-dlp")


class InspectionOptions(_DefaultOptions):

    # Extra options
    reportLocation = None

    def __init__(self, opt=_DefaultOptions(), **kw):
        """ instance-constructor """
        self.init_options(opt, kw)


class PseudoOptions(_DefaultOptions):

    # Extra options
    kmsKeyringId = 'dlpflow-keyring'
    kmsKeyId = 'dlpflow-key-encryption-key-1'
    secretManagerKeyName = 'dlpflow-tinkey-wrapped-key-1'
    fields = None
    target = None

    def __init__(self, opt=_DefaultOptions(), **kw):
        """ instance-constructor """
        self.init_options(opt, kw)


def start_dlp_inspection_pipeline(options: InspectionOptions):

    options.validate()
    options_str = f'--project={options.projectId} \
    --region={options.regionId} \
    --userName={options.userName} \
    --runner=DataflowRunner \
    --serviceAccount={options.serviceAccountPrefix}@{options.projectId}.iam.gserviceaccount.com \
    --gcpTempLocation=gs://{options.tempGcsBucket}/temp \
    --stagingLocation=gs://{options.tempGcsBucket}/staging \
    --tempLocation=gs://{options.tempGcsBucket}/bqtemp \
    --workerMachineType={options.workerMachineType} \
    --subnetwork=https://www.googleapis.com/compute/v1/projects/{options.projectId}/regions/{options.regionId}/subnetworks/{options.subnetworkName} \
    --sampleSize={options.sampleSize} \
    --sourceType={options.sourceType} \
    --csvFirstRowHeader={str.lower(str(options.csvFirstRowHeader))} \
    {"--csvHeaders=" + ",".join(options.csvHeaders) if len(options.csvHeaders) > 0 else ""} \
    --inputPattern={options.source} \
    --reportLocation={options.reportLocation}'

    _run_pipeline('com.google.cloud.solutions.autotokenize.pipeline.DlpInspectionPipeline', options_str.split(' '),
                  stderr=STDOUT if options.logFile is STDOUT else open(options.logFile, mode='w'))


def start_pseudo_pipeline(options: PseudoOptions):

    options.validate()
    options_str = f'--project={options.projectId} \
    --region={options.regionId} \
    --userName={options.userName} \
    --runner=DataflowRunner \
    --serviceAccount={options.serviceAccountPrefix}@{options.projectId}.iam.gserviceaccount.com \
    --tempLocation=gs://{options.tempGcsBucket}/bqtemp \
    --workerMachineType={options.workerMachineType} \
    --mainKmsKeyUri=gcp-kms://projects/{options.projectId}/locations/{options.regionId}/keyRings/{options.kmsKeyringId}/cryptoKeys/{options.kmsKeyId} \
    --keyMaterialType=TINK_GCP_KEYSET_JSON_FROM_SECRET_MANAGER \
    --keyMaterial=projects/{options.projectId}/secrets/{options.secretManagerKeyName}/versions/latest \
    --subnetwork=https://www.googleapis.com/compute/v1/projects/{options.projectId}/regions/{options.regionId}/subnetworks/{options.subnetworkName} \
    --sourceType={options.sourceType} \
    --csvFirstRowHeader={str.lower(str(options.csvFirstRowHeader))} \
    {"--csvHeaders=" + ",".join(options.csvHeaders) if len(options.csvHeaders) > 0 else ""} \
    --inputPattern={options.source} \
    {"--outputDirectory=" if str.startswith(options.target, "gs://") else "--outputBigQueryTable="}{options.target} \
    {" ".join(map(lambda col: "--tokenizeColumns=" + col, options.fields))}'

    _run_pipeline('com.google.cloud.solutions.autotokenize.pipeline.EncryptionPipeline', options_str.split(' '),
                  stderr=STDOUT if options.logFile is STDOUT else open(options.logFile, mode='w'))


def _run_pipeline(pipeline_name, options, stdout=PIPE, stderr=STDOUT):
    p = Popen(['java', '-cp', os.environ['AUTO_TOKENIZE_JAR'], pipeline_name] + options, stdout=stdout, stderr=stderr)

    while True:
        # Wait for some output, read it and print it.
        output = p.stdout.read1(1024).decode('utf-8')
        print(output, end='')

        # Has the subprocess finished yet?
        if p.poll() is not None:
            break

    if p.returncode != 0:
        print("Exited with error code:", p.returncode)
