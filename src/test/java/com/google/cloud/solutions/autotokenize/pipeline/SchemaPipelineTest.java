package com.google.cloud.solutions.autotokenize.pipeline;

import com.google.cloud.solutions.autotokenize.testing.TestResourceLoader;
import org.apache.avro.Schema;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.testing.TestPipeline;
import org.junit.Test;

import java.util.Arrays;

public class SchemaPipelineTest {

    private SchemaPipeline schemaPipeline = new SchemaPipeline(PipelineOptionsFactory.create()
            .as(EncryptionPipelineOptions.class), TestPipeline.create());

    @Test
    public void mapSchemaWithGlobMatch() {
        var schema = new Schema.Parser().parse(TestResourceLoader.classPath().loadAsString("Contacts5kSql_avro_schema.json"));
        var transformed = schemaPipeline.annotateSchema(schema, Arrays.asList("**/contact_*"));
        System.out.println(transformed.toString(true));
    }
}
