package com.google.cloud.solutions.autotokenize.pipeline;

import com.google.cloud.solutions.autotokenize.AutoTokenizeMessages;
import com.google.cloud.solutions.autotokenize.auth.AccessTokenCredentialsFactory;
import com.google.cloud.solutions.autotokenize.common.SourceNames;
import com.google.common.annotations.VisibleForTesting;
import org.apache.avro.Schema;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.io.TextIO;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.beam.sdk.values.TypeDescriptors;

import java.nio.file.FileSystems;
import java.nio.file.Paths;
import java.util.List;

public class SchemaPipeline {

    private final EncryptionPipelineOptions options;
    private final Pipeline pipeline;

    public SchemaPipeline(EncryptionPipelineOptions options, Pipeline pipeline) {
        this.options = options;
        this.pipeline = pipeline;
    }

    public PipelineResult run() {
        if (options.getInputPattern().endsWith(".parquet")) {
            options.setSourceType(AutoTokenizeMessages.SourceType.PARQUET);
        } else if (options.getInputPattern().endsWith(".csv")) {
            options.setSourceType(AutoTokenizeMessages.SourceType.CSV_FILE);
        } else {
            throw new IllegalArgumentException("Unable to infer source type from input pattern: " + options.getInputPattern());
        }
        var schema = pipeline.apply("ReadSchema" + SourceNames.forType(options.getSourceType()).asCamelCase(),
                Create.of(SchemaHelper.readSchemaFromInputFile(options)));

        if (options.getTokenizeGlobPattern() != null && !options.getTokenizeGlobPattern().isEmpty()) {
            schema = schema.apply("MatchGlobPatterns",
                    MapElements.into(schemaType())
                            .via((Schema s) -> annotateSchema(s, options.getTokenizeGlobPattern())));
        }

        schema.apply("SchemaToJson",
                        MapElements.into(TypeDescriptors.strings())
                .via(s -> s.toString(true)))
                .apply("WriteSchema",
                        TextIO.write()
                .to(options.getOutputDirectory() + "/schema").withSuffix(".json").withoutSharding());
        return pipeline.run();
    }

    @VisibleForTesting
    protected Schema annotateSchema(Schema s, List<String> globs) {
        annotateSchema(s.getFields(), "", globs);
        return s;
    }
    private void annotateSchema(List<Schema.Field> fields, String parent, List<String> globs) {
        for (var field: fields) {
            var path = parent + "/" + field.name();
            if (globMatches(path, globs)) {
                field.addProp("globMatch", true);
            }
            if (field.schema().getType() == Schema.Type.RECORD) {
                annotateSchema(field.schema().getFields(), path, globs);
            } else if (field.schema().getType() == Schema.Type.ARRAY) {
                //TODO: Doesn't work
                path = path + "/" + field.schema().getElementType().getName();
                annotateSchema(field.schema().getElementType().getFields(), path, globs);
            }
        }
    }

    /**
     * Return true if the value matches a specified glob pattern
     *
     * Glob syntax follows several simple rules, see:
     * https://docs.oracle.com/javase/tutorial/essential/io/fileOps.html#glob
     */
    private boolean globMatches(String path, List<String> globPatterns) {
        for (var globPattern : globPatterns) {
            if (FileSystems.getDefault().getPathMatcher("glob:" + globPattern).matches(Paths.get(path))) {
                return true;
            }
        }
        return false;
    }

    private TypeDescriptor<Schema> schemaType() {
        return new TypeDescriptor<>() {
        };
    }

    public static void main(String[] args) {

        EncryptionPipelineOptions options = PipelineOptionsFactory.fromArgs(args).as(EncryptionPipelineOptions.class);
        options.setCredentialFactoryClass(AccessTokenCredentialsFactory.class);
        options.setJobName(new UserEnvironmentOptions.JobNameFactory().create(options));

        new SchemaPipeline(options, Pipeline.create(options)).run();
    }
}
