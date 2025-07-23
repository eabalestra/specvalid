

from prompt.prompt_id import PromptID


class Prompt:
    id: PromptID
    template: str
    prompt: str
    format_instructions: str

    class_code: str
    method_code: str
    spec: str

    def __init__(self, id=PromptID.General_V1, class_code="", method_code="", spec=""):
        self.id = id
        self.class_code = class_code
        self.method_code = method_code
        self.spec = spec
        self.format_instructions = ""
        self.instantiate_prompt_template()

    def instantiate_prompt_template(self):
        if self.id == PromptID.General_V1:
            self.template = prompt_template
            self.template += self.get_few_shot_examples(number_of_examples=3)
            prompt_template_section = '''
            [[CODE]]
            {class_code}
            [[METHOD]]
            {method_code}
            [[POSTCONDITION]]
            {spec}

            '''
            prompt_template_section = prompt_template_section.format(
                class_code=self.class_code,
                method_code=self.method_code,
                spec=self.spec
            )
            self.prompt = self.template + prompt_template_section
        elif self.id == PromptID.General_V2:
            pass
        elif self.id == PromptID.NOT_COMPILABLE:
            self.template = "The test that you generated is not compilable. Please fix it."
            self.prompt = self.template

    def get_few_shot_examples(self, number_of_examples=3) -> str:
        answer = "Here are some examples of inputs and corresponding outputs:\n"
        if number_of_examples >= 1:
            for i in range(min(number_of_examples, len(few_shot_examples))):
                answer += few_shot_examples[i] + "\n"
            return answer
        else:
            raise ValueError("Number of examples must be at least 1.")


prompt_template = '''You are an expert in program verification and testing. You are given a Java method and a postcondition assertion for that method.
Based on the method behavior, you will need to confirm that the method meets the postcondition.
If indeed the method meets the postcondition, you MUST output "OK".
If, on the other hand, you determine that the method does NOT meet the postcondition, you MUST output a counterexample, in the form of a jUnit test case. The counterexample test case MUST demonstrate the violation of the postcondition, using input values for the method that, after the execution of the method, make the postcondition invalid. You may provide the reasoning behind your ou

You will receive the input in the following way:
- The source code of the class comes first, after a line containing the text “[[CODE]]”
- The method under test, that the postcondition refers to, comes after the code, preceded by text “[[METHOD]]”
- The postcondition follows after the method, and is preceded by text “[[POSTCONDITION]]” (note: postconditions may include quantifiers like size(X) – returns the size of the collection X; pairwiseEqual(seq1, seq2) - True iff seq1 and seq2 have the same length, and every seq1[i] == seq2[i]; isReverse(seq1, seq2) - True iff seq1 is the reverse of seq2, typeArray(X) – returns the type of the array X; getElement(X, i) – returns the i-th element of the array X; old(X) – returns the value of X before executing the method under test; 

The output must be produced as follows:
- After text “[[VERDICT]]”, you will output “OK” if no counterexample for the method and postcondition exist, and “FAILED” otherwise.
- If verdict was “[[FAILED]]”, output the counterexample after the verdict, preceded by text “[[TEST]]”, in JUnit format.
'''

few_shot_examples = ["""[[CODE]]
package examples;

public class SimpleMethods {
    /**
      * Compute the minimum of two values
      *
      * @param a first value
      * @param b second value
      * @return a if a is lesser or equal to b, b otherwise
      */
    public int getMin(final int a, final int b) {
      final int result;
        if (a <= b) {
            result = a;
        } else {
            result = b;
        }
        return result;
    }
}
[[METHOD]]
public int getMin(final int a, final int b) {
  final int result;
    if (a <= b) {
        result = a;
    } else {
        result = b;
    }
    return result;
}
[[POSTCONDITION]]
assertTrue(a != b || b <= result);
[[VERDICT]]
OK
[[TEST]]
NONE""",
                     """
[[CODE]]
package jts;
/**
  * <p>Operations on boolean primitives and Boolean objects.</p>
  *
  * <p>This class tries to handle {@code null} input gracefully.
  * An exception will not be thrown for a {@code null} input.
  * Each method documents its behaviour in more detail.</p>
  *
  * <p>#ThreadSafe#</p>
  * @since 2.0
  */
public class MathUtil {


      /**
        * Clamps an <tt>int</tt> value to a given range.
        * @param x the value to clamp
        * @param min the minimum value of the range
        * @param max the maximum value of the range
        * @return the clamped value
        */
      public static int clamp(int x, int min, int max)
      {
        int result;
        if (x < min) {
            result = min;
        } else if (x > max) {
            result = max;
        } else {
            result = x;
        }

        assert (true);
        return result;
      }
}
[[METHOD]]
public static int clamp(int x, int min, int max)
{
    int result;
    if (x < min) {
        result = min;
    } else if (x > max) {
        result = max;
    } else {
        result = x;
    }
    return result;
}
[[POSTCONDITION]]
assertTrue(orig(max) != -1 || result != 0);
[[VERDICT]]
FAILED
[[TEST]]
@Test
public void testClamp_1() {
    int x = -1;
    int min = 0;
    int max = -1;
    int origMax = max;

    int result = jts.MathUtil.clamp(x, min, max);

    assertTrue(origMax != -1 || result != 0);
}

""",

                     """
[[CODE]]
package DataStructures;


import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;


/**
  * @author Facundo Molina <fmolina@dc.exa.unrc.edu.ar>
  */
public class List implements Serializable {


  //static final long serialVersionUID = 20200617L;


  int x;
  List next;


  static final int SENTINEL = Integer.MAX_VALUE;


  List(int x, List next) {
    this.x = x;
    this.next = next;
  }


  public List() {
    this(SENTINEL, null);
  }


  public void insert(int data) {
    if (data > this.x) {
      next.insert(data);
    } else {
      next = new List(x, next);
      x = data;
    }
  }


  public boolean repOk() {
    Set<List> visited = new HashSet<List>();
    List curr = this;
    while (curr.x != SENTINEL) {
      // The list should acyclic
      if (!visited.add(curr))
        return false;
      // The list should be sorted
      List curr_next = curr.next;
      if (curr.x > curr_next.x)
        return false;


      curr = curr_next;
    }
    return true;
  }


  @Override
  public String toString() {
    if (x == SENTINEL) {
      return "null";
    } else {
      return x + ", " + next.toString();
    }
  }


}
[[METHOD]]
public void insert(int data) {
    if (data > this.x) {
      next.insert(data);
    } else {
      next = new List(x, next);
      x = data;
    }
}
[[POSTCONDITION]]
assertTrue(this.x != this.next.next.x + orig(this.next.next.x));
[[VERDICT]]
FAILED
[[TEST]]
@Test
public void testInsert_1() {
    DataStructures.List list = new DataStructures.List();

    list.insert(-9);
    list.insert(-9);

    DataStructures.List origList = list.clone();

    list.insert(-18);

    assertTrue(list.x != list.next.next.x + origList.next.next.x);
}
"""]
