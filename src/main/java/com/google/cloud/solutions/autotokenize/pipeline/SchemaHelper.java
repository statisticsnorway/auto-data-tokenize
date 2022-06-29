package com.google.cloud.solutions.autotokenize.pipeline;

import com.google.cloud.solutions.autotokenize.AutoTokenizeMessages;
import com.google.cloud.solutions.autotokenize.common.CsvRowFlatRecordConvertors;
import com.google.common.flogger.GoogleLogger;
import org.apache.avro.Schema;
import org.apache.beam.sdk.io.FileSystems;
import org.apache.parquet.avro.AvroParquetReader;
import org.apache.parquet.io.DelegatingSeekableInputStream;
import org.apache.parquet.io.InputFile;
import org.apache.parquet.io.SeekableInputStream;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.channels.Channels;
import java.nio.channels.SeekableByteChannel;
import java.util.Arrays;

import static com.google.common.base.Preconditions.*;
import static org.apache.commons.lang3.StringUtils.*;

public class SchemaHelper {

    public static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

    public static Schema readSchemaFromInputFile(EncryptionPipelineOptions options) {
        checkArgument(
                isNotBlank(options.getSchema())
                        || AutoTokenizeMessages.SourceType.PARQUET.equals(options.getSourceType())
                        || (AutoTokenizeMessages.SourceType.CSV_FILE.equals(options.getSourceType()) && options.getCsvFirstRowHeader())
                        || (AutoTokenizeMessages.SourceType.CSV_FILE.equals(options.getSourceType())
                        && options.getCsvHeaders() != null
                        && !options.getCsvHeaders().isEmpty()),
                "Provide Source's Avro Schema or headers for CSV_FILE.");

        Schema inputSchema;
        try {
            if (AutoTokenizeMessages.SourceType.PARQUET.equals(options.getSourceType())) {
                logger.atInfo().log("Will try to infer schema from Parquet file");
                try (var fc = (SeekableByteChannel) FileSystems.open(FileSystems.matchNewResource(options.getInputPattern(), false))) {
                    var parquetReader = AvroParquetReader.genericRecordReader(new BeamParquetInputFile(fc));
                    inputSchema = parquetReader.read().getSchema();
                    logger.atInfo().log("Inferred schema: %s", inputSchema.toString(true));
                }
            } else if (options.getSchema() != null) {
                inputSchema = new Schema.Parser().parse(options.getSchema());
            } else if (options.getCsvFirstRowHeader()) {
                logger.atInfo().log("Will try to infer schema from first row in CSV file");
                try (var stream = Channels.newInputStream(FileSystems.open(FileSystems.matchNewResource(
                        options.getInputPattern(), false)))) {
                    var reader = new BufferedReader(new InputStreamReader(stream));
                    var headers = reader.readLine();
                    var separator = headers.contains(";") ? ";" : ",";
                    inputSchema = CsvRowFlatRecordConvertors.makeCsvAvroSchema(Arrays.asList(headers.split(separator)));
                    logger.atInfo().log("Inferred schema: %s", inputSchema.toString(true));
                }
            } else {
                inputSchema = CsvRowFlatRecordConvertors.makeCsvAvroSchema(options.getCsvHeaders());
            }
        } catch (IOException e) {
            throw new IllegalArgumentException("Error reading schema URI", e);
        }
        return inputSchema;
    }

    private static class BeamParquetInputFile implements InputFile {
        private final SeekableByteChannel seekableByteChannel;

        BeamParquetInputFile(SeekableByteChannel seekableByteChannel) {
            this.seekableByteChannel = seekableByteChannel;
        }

        @Override
        public long getLength() throws IOException {
            return seekableByteChannel.size();
        }

        @Override
        public SeekableInputStream newStream() {
            return new DelegatingSeekableInputStream(Channels.newInputStream(seekableByteChannel)) {

                @Override
                public long getPos() throws IOException {
                    return seekableByteChannel.position();
                }

                @Override
                public void seek(long newPos) throws IOException {
                    seekableByteChannel.position(newPos);
                }
            };
        }
    }

}
