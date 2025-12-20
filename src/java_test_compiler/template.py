TEST_TEMPLATE = """
import static org.junit.Assert.*;
import org.junit.Test;
import java.io.*;
import java.lang.reflect.*;
import java.math.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;
import java.util.stream.*;

public class GeneratedTest {
    {test_method}
}
"""
