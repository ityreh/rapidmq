package de.ityreh.rapidmq.messaging;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import io.micrometer.tracing.propagation.Propagator;

@Component
public class RabbitConsumer {
    private final Tracer tracer;
    private final Propagator propagator;
    private final ObservationRegistry observationRegistry;
    private static final Logger logger = LoggerFactory.getLogger(RabbitConsumer.class);

    public RabbitConsumer(Tracer tracer, Propagator propagator,
            ObservationRegistry observationRegistry) {
        this.tracer = tracer;
        this.propagator = propagator;
        this.observationRegistry = observationRegistry;
    }

    @RabbitListener(queues = "${app.rabbitmq.queue}")
    public void handle(Message message) {
        Span.Builder spanBuilder =
                propagator.extract(message.getMessageProperties(), MESSAGE_PROPERTIES_GETTER);

        Span span = spanBuilder != null ? spanBuilder.start() : tracer.nextSpan();
        span.name("rabbitmq.consume");
        span.start();

        Observation observation = Observation.start("rabbitmq.consume", observationRegistry);

        try (Tracer.SpanInScope spanScope = tracer.withSpan(span);
                Observation.Scope observationScope = observation.openScope()) {
            String body = new String(message.getBody());
            logger.info("Consumed message: {}", body);
        } finally {
            observation.stop();
            span.end();
        }
    }

    private static final Propagator.Getter<MessageProperties> MESSAGE_PROPERTIES_GETTER =
            new Propagator.Getter<MessageProperties>() {
                @Override
                public String get(MessageProperties carrier, String key) {
                    if (carrier == null || carrier.getHeaders() == null) {
                        return null;
                    }
                    Object value = carrier.getHeaders().get(key);
                    return value == null ? null : value.toString();
                }
            };
}
